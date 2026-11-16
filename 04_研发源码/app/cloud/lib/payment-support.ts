const KINDS = ['duplicate-charge','payment-missing','restore-failed','cancel-renewal'];
const STATUSES = ['submitted','accepted','resolved'];
const ORDER = `SELECT id,environment,payment_status AS paymentStatus,fulfillment_status AS fulfillmentStatus,
total_minor AS totalMinor,refunded_minor AS refundedMinor,currency
FROM commerce_orders WHERE id=? AND owner=? AND environment='sandbox'`;
const EVENTS = `SELECT id,kind,amount_minor AS amountMinor,currency,created FROM commerce_payment_events
WHERE order_id=? AND owner=? AND environment='sandbox' AND status='applied' ORDER BY created,id`;
const DDL = [
 `CREATE TABLE IF NOT EXISTS payment_support_tickets(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, order_id TEXT REFERENCES commerce_orders(id),
 event_id TEXT REFERENCES commerce_payment_events(id), kind TEXT NOT NULL
 CHECK(kind IN ('duplicate-charge','payment-missing','restore-failed','cancel-renewal')),
 message TEXT NOT NULL, request_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'submitted'
 CHECK(status IN ('submitted','accepted','resolved')), version INTEGER NOT NULL DEFAULT 1,
 created INTEGER NOT NULL, updated INTEGER NOT NULL, UNIQUE(owner,request_id))`,
 'CREATE INDEX IF NOT EXISTS payment_support_owner ON payment_support_tickets(owner,created DESC,id DESC)',
 'CREATE INDEX IF NOT EXISTS payment_support_queue ON payment_support_tickets(status,created DESC,id DESC)',
 `CREATE TABLE IF NOT EXISTS payment_support_actions(
 ticket_id TEXT NOT NULL REFERENCES payment_support_tickets(id), version INTEGER NOT NULL,
 actor TEXT NOT NULL, request_id TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('accepted','resolved')), reply TEXT NOT NULL, created INTEGER NOT NULL,
 PRIMARY KEY(ticket_id,version), UNIQUE(actor,request_id))`,
 `CREATE TRIGGER IF NOT EXISTS payment_support_advance BEFORE INSERT ON payment_support_actions
 BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM payment_support_tickets WHERE id=NEW.ticket_id
 AND version=NEW.version-1 AND ((status='submitted' AND NEW.status='accepted')
 OR (status='accepted' AND NEW.status='resolved'))) THEN RAISE(ABORT,'payment_support_stale') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle l JOIN payment_support_tickets t
 ON t.owner=l.owner WHERE t.id=NEW.ticket_id AND l.status='closed')
 THEN RAISE(ABORT,'payment_support_closed') END;
 UPDATE payment_support_tickets SET status=NEW.status,version=NEW.version,updated=NEW.created
 WHERE id=NEW.ticket_id;
 END`,
];

export async function initPaymentSupport(a:any) {
 if (!await a.one("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='payment_support_advance'"))
  await a.db.batch(DDL.map(sql => a.stmt(sql)));
}

class PaymentSupport {
 constructor(private a:any, private fail:(status:number,message:string)=>never) {}

 field(value:unknown, limit:number, required=true) {
  if (typeof value !== 'string') return this.fail(400,'支付客服表单格式错误。');
  value = value.trim();
  const field = value as string;
  if (new TextEncoder().encode(field).length > limit || (required && !field) ||
      /[\x00-\x08\x0b\x0c\x0e-\x1f\uD800-\uDFFF]/u.test(field))
   return this.fail(400,'支付客服表单内容无效或过长。');
  return field;
 }

 async order(orderId:string, owner:string) {
  const order = await this.a.one(ORDER,orderId,owner);
  if (!order) return this.fail(404,'找不到此订单。');
  return {order,events:await this.a.all(EVENTS,orderId,owner)};
 }

 async ticket(id:string, owner:string|null) {
  const sql = 'SELECT * FROM payment_support_tickets WHERE id=?';
  const row = owner === null ? await this.a.one(sql,id) : await this.a.one(sql+' AND owner=?',id,owner);
  if (!row) return this.fail(404,'找不到此支付客服工单。');
  return row;
 }

 summary(row:any) {
  return {id:row.id,orderId:row.order_id,kind:row.kind,status:row.status,version:row.version,created:row.created,updated:row.updated};
 }

 async serialize(row:any, history?:any[]) {
  const replies = history ?? await this.a.all('SELECT status,reply,created FROM payment_support_actions WHERE ticket_id=? AND version<=? ORDER BY version',row.id,row.version);
  return {...this.summary(row),eventId:row.event_id,message:row.message,replies};
 }

 async create(owner:string, data:any) {
  const kind = this.field(data.kind,32);
  if (!KINDS.includes(kind)) return this.fail(400,'请选择支付问题类型。');
  const orderId = this.field(data.orderId === undefined ? '' : data.orderId,80,false) || null;
  const eventId = this.field(data.eventId === undefined ? '' : data.eventId,80,false) || null;
  const message = this.field(data.message === undefined ? '' : data.message,3000,false);
  const request = this.field(data.requestId,100);
  const find = () => this.a.one('SELECT * FROM payment_support_tickets WHERE owner=? AND request_id=?',owner,request);
  let row = await find();
  if (!row) {
   const summary = orderId ? await this.order(orderId,owner) : null;
   if (eventId && !summary?.events.some((event:any) => event.id === eventId))
    return this.fail(404,'找不到此订单的支付记录。');
   if (!orderId && !message) return this.fail(400,'未关联订单时，请补充问题说明。');
   const now = Date.now();
   await this.a.run(`INSERT INTO payment_support_tickets
    (id,owner,order_id,event_id,kind,message,request_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?)
    ON CONFLICT(owner,request_id) DO NOTHING`,crypto.randomUUID(),owner,orderId,eventId,kind,message,request,now,now);
   row = await find();
  }
  if (row.order_id !== orderId || row.event_id !== eventId || row.kind !== kind || row.message !== message)
   return this.fail(409,'该提交编号已用于其他内容。');
  return {ticket:await this.serialize(row)};
 }

 async act(actor:string, id:string, data:any) {
  const request = this.field(data.requestId,100);
  const status = this.field(data.status,16);
  const reply = this.field(data.reply === undefined ? '' : data.reply,3000,status === 'resolved');
  const version = data.version;
  if (![1,2].includes(version) || !['accepted','resolved'].includes(status))
   return this.fail(400,'工单状态或版本无效。');
  const row = await this.ticket(id,null);
  const find = () => this.a.one('SELECT * FROM payment_support_actions WHERE actor=? AND request_id=?',actor,request);
  let previous = await find();
  if (!previous) {
   if (row.version !== version || !((row.status === 'submitted' && status === 'accepted') || (row.status === 'accepted' && status === 'resolved')))
    return this.fail(409,'工单已更新，请刷新后处理。');
   try {
    await this.a.run('INSERT INTO payment_support_actions VALUES(?,?,?,?,?,?,?)',id,version+1,actor,request,status,reply,Date.now());
   } catch (error) {
    if (String(error).includes('payment_support_closed')) return this.fail(409,'该账号已关闭，无法继续处理此工单。');
    if (!/payment_support_stale|UNIQUE constraint failed: payment_support_actions/.test(String(error))) throw error;
    previous = await find();
    if (!previous) return this.fail(409,'工单已更新，请刷新后处理。');
   }
  }
  if (previous && (previous.ticket_id !== id || previous.version !== version+1 || previous.status !== status || previous.reply !== reply))
   return this.fail(409,'该操作编号已用于其他内容。');
  return {ticket:await this.serialize(await this.ticket(id,null))};
 }

 async list(owner:string|null, query:URLSearchParams) {
  const scope:string[] = [], args:any[] = [];
  if (owner !== null) { scope.push('owner=?'); args.push(owner); }
  const status = query.get('status');
  if (status) {
   if (!STATUSES.includes(status)) return this.fail(400,'工单状态无效。');
   scope.push('status=?'); args.push(status);
  }
  const before = query.get('before');
  if (before) {
   const row = await this.ticket(before,owner);
   scope.push('(created,id)<(?,?)'); args.push(row.created,row.id);
  }
  const where = scope.length ? ' WHERE '+scope.join(' AND ') : '';
  const rows = await this.a.all('SELECT * FROM payment_support_tickets'+where+' ORDER BY created DESC,id DESC LIMIT 26',...args);
  const page = rows.slice(0,25), next = rows.length>25 ? rows[24].id : null;
  if (owner === null || !page.length) return {items:page.map((row:any) => this.summary(row)),next};
  const histories = new Map<string,any[]>();
  const replies = await this.a.all('SELECT ticket_id,version,status,reply,created FROM payment_support_actions WHERE ticket_id IN ('+page.map(() => '?').join(',')+') ORDER BY ticket_id,version',...page.map((row:any) => row.id));
  for (const reply of replies) {
   if (!histories.has(reply.ticket_id)) histories.set(reply.ticket_id,[]);
   histories.get(reply.ticket_id)!.push(reply);
  }
  const items = await Promise.all(page.map((row:any) => this.serialize(row,
   (histories.get(row.id) ?? []).filter(reply => reply.version<=row.version).map(({status,reply,created}) => ({status,reply,created})))));
  return {items,next};
 }
}

export async function paymentSupportRoute(a:any, path:string, method:string, fail:(status:number,message:string)=>never) {
 const admin = path.startsWith('/api/admin/payment-support/');
 const prefix = admin ? '/api/admin/payment-support/' : '/api/payment-support/';
 if (!path.startsWith(prefix)) return undefined;
 const actor = a.require(admin ? ['admin'] : undefined).id;
 await a.rate('payment-support:'+(method === 'GET' ? 'read:' : 'write:')+actor,method === 'GET' ? 180 : 30);
 const service = new PaymentSupport(a,fail), owner = admin ? null : actor, subpath = path.slice(prefix.length);
 if (subpath === 'tickets') {
  if (method === 'GET') return service.list(owner,a.url.searchParams);
  if (method === 'POST' && !admin) return service.create(actor,await a.body());
 }
 const order = /^orders\/([^/]+)$/.exec(subpath);
 if (order && !admin && method === 'GET') return service.order(order[1],actor);
 const ticket = /^tickets\/([^/]+)(\/actions)?$/.exec(subpath);
 if (ticket?.[2] && admin && method === 'POST') return service.act(actor,ticket[1],await a.body());
 if (ticket && !ticket[2] && method === 'GET') {
  const row = await service.ticket(ticket[1],owner);
  const accountClosed = admin ? Boolean(await a.one("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",row.owner)) : undefined;
  return {ticket:await service.serialize(row),payment:row.order_id ? await service.order(row.order_id,row.owner) : null,
   ...(admin ? {accountClosed} : {})};
 }
 return fail(404,'找不到此支付客服功能。');
}
