const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {makeHarness} = require('./负责人优化建议-交易测试工具.cjs');

const h = makeHarness();
const {api, check} = h;
const environment = 'sandbox';
const address = {name:'合成收件人',country:'CN',city:'测试市',address:'测试路 1 号',postalCode:'000000'};
const skuCode = suffix => 'variant-'+h.runId+'-'+suffix;
const option = value => [{name:'尺寸 / Size',value}];
const productInput = {
 title:'规格专项测试商品',type:'physical',environment,status:'published',
 currency:'CNY',shippingCountries:['CN'],shippingMinor:20,taxMinor:10,
};
const item = (variant, quantity=1) => ({skuId:variant.skuId,quantity});
const order = (items, requestId=crypto.randomUUID()) => ({environment,items,requestId,shippingAddress:address});
const editable = ({skuId,sku,priceMinor,stock,options,active}) => ({skuId,sku,priceMinor,stock,options,active,expectedStock:stock});
const getProduct = async (ctx,id) => (await api(ctx,'admin/commerce')).data.products.find(p=>p.id===id);

async function main(){
 await h.start();
 const {admin,user,other,anonymous}=await h.seed();
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const created=(await api(admin,'admin/commerce/products',{...productInput,sku:skuCode('small'),stock:7,priceMinor:100})).data.item;
 const firstOrder=(await api(user,'commerce/orders',order([item(created)]))).data;
 let product,small,large,soldOut,placed;
 await check('原单规格商品可升级，旧 SKU ID 和原订单保留',async()=>{
  const current=await getProduct(admin,created.id);
  const variants=[
   {...editable(current.variants[0]),options:option('小号 / Small')},
   {sku:skuCode('large'),stock:3,priceMinor:280,options:option('大号 / Large')},
   {sku:skuCode('sold-out'),stock:0,priceMinor:350,options:option('特大号 / Extra large')},
  ];
  product=(await api(admin,'admin/commerce/products',{...productInput,id:created.id,version:current.version,variants})).data.item;
  [small,large,soldOut]=['small','large','sold-out'].map(name=>product.variants.find(v=>v.sku===skuCode(name)));
  assert.equal(small.skuId,created.skuId);
  assert.equal(small.reserved,1);
  assert.equal(large.reserved,0);
  const result=(await api(user,'commerce/orders/'+firstOrder.id)).data;
  assert.deepEqual(result.items[0].options,[]);
  assert.equal(result.items[0].priceMinor,100);
  await api(other,'commerce/orders/'+firstOrder.id,undefined,'GET',404);
 });
 await check('目录每商品一条，规格价格库存独立，生产目录隔离',async()=>{
  const catalog=(await api(anonymous,'commerce/catalog?environment=sandbox')).data.items;
  assert.equal(catalog.filter(p=>p.id===product.id).length,1);
  const row=catalog.find(p=>p.id===product.id);
  assert.equal(row.variants.length,3);
  assert.equal(row.variants.find(v=>v.skuId===soldOut.skuId).purchasable,false);
  assert.equal(row.variants.find(v=>v.skuId===large.skuId).priceMinor,280);
  assert(!(await api(anonymous,'commerce/catalog')).data.items.some(p=>p.id===product.id));
 });
 await check('拒绝重复组合、跨商品SKU和遗漏历史规格',async()=>{
  const current=await getProduct(admin,product.id);
  const variants=current.variants.map(editable);
  const update={...productInput,id:current.id,version:current.version};
  const foreign=(await api(admin,'admin/commerce/products',{...productInput,sku:skuCode('foreign'),stock:1,priceMinor:10})).data.item;
  await api(admin,'admin/commerce/products',{...update,variants:[...variants,{sku:skuCode('dup'),stock:1,priceMinor:1,options:small.options}]},'POST',400);
  await api(admin,'admin/commerce/products',{...update,variants:[...variants,editable(foreign.variants[0])]},'POST',400);
  await api(admin,'admin/commerce/products',{...update,variants:variants.slice(1)},'POST',409);
  await api(other,'admin/commerce/products',{...update,variants},'POST',403);
  assert.equal((await getProduct(admin,product.id)).version,current.version);
 });
 await check('购物车按 SKU 分行并拒绝缺货与越权',async()=>{
  await api(user,'commerce/cart',{environment,items:[item(small),item(large)]},'PATCH');
  const rows=(await api(user,'commerce/cart?environment=sandbox')).data.items;
  assert.deepEqual(new Set(rows.map(r=>r.skuId)),new Set([small.skuId,large.skuId]));
  assert.deepEqual((await api(other,'commerce/cart?environment=sandbox')).data.items,[]);
  await api(user,'commerce/cart',{environment,items:[item(soldOut)]},'PATCH',409);
  await api(user,'commerce/orders',order([item(soldOut)]),'POST',409);
 });
 await check('服务端按选中规格核价，订单项保存规格和成交价',async()=>{
  const body=order([{...item(small),priceMinor:1,options:option('伪造')},item(large,2)]);
  placed=(await api(user,'commerce/orders',body)).data;
  assert.equal(placed.subtotalMinor,660);
  assert.equal(placed.totalMinor,750);
  assert.deepEqual(placed.items.find(i=>i.skuId===large.skuId).options,large.options);
  assert.equal(placed.items.find(i=>i.skuId===small.skuId).sku,small.sku);
  assert.equal((await api(user,'commerce/orders',body)).data.id,placed.id);
  const current=await getProduct(admin,product.id);
  const variants=current.variants.map(v=>v.skuId===large.skuId?{...editable(v),stock:1}:editable(v));
  await api(admin,'admin/commerce/products',{...productInput,id:product.id,version:current.version,variants},'POST',409);
 });
 await check('不同SKU独立预占，库存竞争只允许一笔成功',async()=>{
  const results=await Promise.all([user,other].map(ctx=>api(ctx,'commerce/orders',order([item(large)]),'POST',null)));
  assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);
  assert.equal((await getProduct(admin,product.id)).variants.find(v=>v.skuId===large.skuId).reserved,3);
 });
 await check('下架仅阻止新购买，旧订单快照、付款和按项退款可追溯',async()=>{
  const current=await getProduct(admin,product.id);
  const variants=current.variants.map(v=>v.skuId===large.skuId?{...editable(v),active:false,priceMinor:490,options:option('新版规格')}:editable(v));
  const updated=(await api(admin,'admin/commerce/products',{...productInput,id:product.id,version:current.version,variants})).data.item;
  assert.equal(updated.variants.find(v=>v.skuId===large.skuId).active,false);
  assert(!(await api(anonymous,'commerce/catalog?environment=sandbox')).data.items.find(v=>v.id===product.id).variants.some(v=>v.skuId===large.skuId));
  await api(user,'commerce/orders',order([item(large)]),'POST',409);
  await api(user,'commerce/cart',{environment,items:[item(small)]},'PATCH');
  const paid=(await api(user,'commerce/orders/'+placed.id+'/sandbox-pay',{requestId:crypto.randomUUID()})).data;
  assert.equal(paid.paymentStatus,'paid');
  const original=paid.items.find(v=>v.skuId===large.skuId);
  assert.equal(original.priceMinor,280);
  assert.deepEqual(original.options,large.options);
  const refund=(await api(admin,'admin/commerce/orders/'+paid.id+'/refund',{requestId:crypto.randomUUID(),items:[{itemId:original.id,quantity:1}]})).data;
  assert.equal(refund.refundedMinor,310);
  assert.equal(refund.inventoryEvents.at(-1).skuId,large.skuId);
  assert.equal((await getProduct(admin,product.id)).variants.find(v=>v.skuId===large.skuId).stock,2);
 });
 await check('后台原生控件新增规格，APP 四语选择、加入购物车和订单回显',async()=>{
  const adminPage=(await h.browserContext(await admin.storageState())).page;
  await adminPage.goto(h.base+'/admin');
  await adminPage.locator('[data-nav=commerce]').first().click();
  const editor=adminPage.locator('#co-product-form');
  await editor.locator('[name=title]').fill('浏览器规格样品');
  await editor.locator('[name=type]').selectOption('physical');
  await editor.locator('[name=status]').selectOption('published');
  await editor.locator('[name=shippingCountries]').fill('CN');
  await editor.locator('[data-co-admin=add-sku]').click();
  const options=['青玉 / Celadon','深墨 / Dark ink'];
  for(const [i,value] of options.entries()){
   const row=editor.locator('[data-co-sku-row]').nth(i);
   await row.locator('[name=variantSku]').fill(skuCode('ui-'+i));
   await row.locator('[name=variantPrice]').fill(String(120+i*80));
   await row.locator('[name=variantStock]').fill('6');
   await row.locator('[name=optionName]').first().fill('颜色 / Color');
   await row.locator('[name=optionValue]').first().fill(value);
  }
  const saved=adminPage.waitForResponse(r=>r.url().endsWith('/api/admin/commerce/products')&&r.request().method()==='POST');
  await editor.locator('[type=submit]').click();
  const response=await saved;
  const data=await response.json();
  assert.equal(response.status(),200,data.error);
  const p=data.item,wanted=p.variants.find(v=>v.sku===skuCode('ui-1'));
  assert.equal(p.variants.length,2);
  await editor.locator('[data-co-sku-row]').nth(1).waitFor({state:'detached'});
  await adminPage.locator('[data-co-admin=edit][data-id="'+p.id+'"]').click();
  await h.capture(adminPage,'后台规格编辑');
  const browserBuyer=await h.context();
  await api(browserBuyer,'auth/register',{username:'variant_ui_'+h.runId,password:crypto.randomUUID(),name:'规格浏览器买家'});
  const page=(await h.browserContext(await browserBuyer.storageState())).page;
  for(const [lang,width,mode] of [['zh',360,'night'],['zh-Hant',390,'day'],['en',360,'day'],['bo',390,'night'],['en',1100,'night']]){
   await page.setViewportSize({width,height:850});
   await page.goto(h.base+'/experience?page=commerceShop&lang='+lang+'&mode='+mode);
   await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();
   await page.locator('[data-commerce-action=product][data-id="'+p.id+'"]').click();
   const add=page.locator('[data-commerce-action=add]');
   assert(await add.isDisabled());
   await page.locator('[data-commerce-variant]').selectOption(wanted.skuId);
   assert(await add.isEnabled());
   assert.equal(await add.getAttribute('data-sku-id'),wanted.skuId);
   assert.equal(await page.locator('.co-sku-fact dd').innerText(),options[1]);
   await page.evaluate(()=>document.fonts.ready.then(()=>null));
   assert(await page.locator('.co-product-detail').evaluate(el=>el.scrollWidth<=el.clientWidth+2));
   await h.capture(page,'商品规格-'+lang+'-'+width);
  }
  await page.locator('[data-commerce-action=add]').click();
  const form=page.locator('#co-checkout-form');
  await form.waitFor();
  await page.waitForFunction(()=>!coState().loading&&!coState().busy&&coState().loaded);
  assert((await page.locator('.co-cart-items').innerText()).includes(options[1]));
  for(const [field,value] of Object.entries(address))await form.locator('[name='+field+']').fill(value);
  await form.locator('[name=accept]').check();
  const checkout=page.waitForResponse(r=>r.url().endsWith('/api/commerce/orders')&&r.request().method()==='POST');
  await form.locator('[type=submit]').click();
  const checkoutResponse=await checkout;
  assert.equal(checkoutResponse.status(),200,checkoutResponse.ok()?'':await checkoutResponse.text());
  await page.locator('.co-order-lines').waitFor();
  await page.waitForFunction(()=>!coState().loading&&!coState().busy);
  assert((await page.locator('.co-order-lines').innerText()).includes(options[1]));
  await h.capture(page,'订单规格快照');
 });
}

main().then(()=>h.finish(),error=>h.finish(error));
