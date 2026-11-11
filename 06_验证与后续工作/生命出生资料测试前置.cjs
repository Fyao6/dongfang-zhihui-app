// Legitimate synthetic birth-data precondition for broad regression suites.
// This fills and submits the actual unified form; it does not seed storage or bypass validation.
const assert=require('node:assert/strict');
const fixture={name:'QA_FULL_REGRESSION',date:'1990-01-01',sex:'male',time:'12:00'};
const lifeRoutes=new Set(['lifeResult','ziweiChart','classicsWisdom','westernAstrology','lifeReview']);
async function available(page){return page.evaluate(()=>typeof lbProfile==='function');}
async function ready(page){await page.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);}
async function setLifeBirth(page,values=fixture){
 assert(await available(page),'Unified birth entry is not available');
 await page.evaluate(()=>navigate('lifeResult'));await ready(page);
 let form=page.locator('#lb-birth-form');
 if(!await form.count()){await page.locator('[data-lb-action=edit]').first().click();await ready(page);}
 await form.waitFor();
 for(const [key,value]of Object.entries(values)){
  if(!['name','date','sex','time'].includes(key))continue;
  const field=form.locator('[name="'+key+'"]');if(key==='ambiguity'&&(!await field.count()||!await field.isVisible()))continue;assert.equal(await field.count(),1,'Missing actual birth input '+key);
  // Disclosures are display-only. Opening them leaves actual form validation and storage intact.
  await field.evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  if(await field.evaluate(e=>e.tagName==='SELECT'))await field.selectOption(String(value));else await field.fill(String(value));
 }
 await form.locator('button[type=submit]').click();await ready(page);await page.locator('.fl-life').waitFor();
 assert.equal(await page.evaluate(()=>lbProfile()?.date),values.date);
 if(Object.hasOwn(values,'time'))assert.equal(await page.evaluate(()=>lbProfile()?.time),values.time);
}
async function ensureLifeBirth(page,route='lifeResult'){
 if(!lifeRoutes.has(route)||!await available(page))return;
 if(await page.evaluate(()=>!!lbProfile()))return;
 await setLifeBirth(page,fixture);
}
async function setChartRules(page,kind,values={}){
 const form=page.locator('form[data-lb-options='+kind+']');await form.waitFor({state:'attached'});
 await form.evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
 for(const [key,value]of Object.entries(values))await form.locator('[name='+key+']').selectOption(String(value));
 await form.locator('button[type=submit]').click();await ready(page);
}
module.exports={fixture,lifeRoutes,available,setLifeBirth,ensureLifeBirth,setChartRules};
