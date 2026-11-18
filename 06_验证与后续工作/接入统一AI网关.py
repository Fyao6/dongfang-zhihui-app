"""Integrate the real transport gateway, owner-scoped metadata and explicit provider UI."""
from pathlib import Path
R=Path(__file__).resolve().parent.parent;A=R/'04_研发源码/app';F=A/'r4';C=A/'cloud'
def patch(p,old,new):
 s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(str(p),old[:100])
 p.write_text(s.replace(old,new,1),encoding='utf-8')
patch(F/'backend/server.py','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError','\n'.join([
 'from zoneinfo import ZoneInfo, ZoneInfoNotFoundError',
 'try:',
 '    from ai_gateway import AIGateway, StreamReply, init_schema as init_ai_gateway_schema',
 'except ModuleNotFoundError:',
 '    import importlib.util',
 "    _ai_gateway_spec = importlib.util.spec_from_file_location('eastern_ai_gateway', Path(__file__).with_name('ai_gateway.py'))",
 '    _ai_gateway_module = importlib.util.module_from_spec(_ai_gateway_spec)',
 '    _ai_gateway_spec.loader.exec_module(_ai_gateway_module)',
 '    AIGateway, StreamReply, init_ai_gateway_schema = _ai_gateway_module.AIGateway, _ai_gateway_module.StreamReply, _ai_gateway_module.init_schema']))
patch(F/'backend/server.py','            init_privacy_schema(db)','            init_privacy_schema(db)\n            init_ai_gateway_schema(db)')
patch(F/'backend/server.py','        def api(self, method, path):','\n'.join([
 '        def api(self, method, path):',
 '            gateway_result = AIGateway(store, self, ApiError, rate_limit).route(method, path)',
 '            if gateway_result is not None:',
 '                return gateway_result']))
patch(F/'backend/server.py','                result = self.api(method, path)\n                if result is not None:', '                result = self.api(method, path)\n                if isinstance(result, StreamReply):\n                    return result.send(self)\n                if result is not None:')
patch(F/'backend/server.py',"user=public_user(self.user), aiReady=bool(ai.get('enabled') and ai.get('apiKey') and ai.get('model')))","user=public_user(self.user), aiReady=bool(ai.get('enabled') and ai.get('apiKey') and ai.get('model')), aiGatewayReady=bool(store.setting('ai_gateway').get('enabled')))")
patch(C/'lib/eastern-api.ts',"import seed from '../generated/seed.json';","import {initAIGateway,aiGatewayRoute} from './ai-gateway';\nimport seed from '../generated/seed.json';")
patch(C/'lib/eastern-api.ts','await initPrivacy(this);','await initPrivacy(this);await initAIGateway(this);')
patch(C/'lib/eastern-api.ts',"m=this.method;const video=","m=this.method;const gateway=await aiGatewayRoute(this,p,m,fail);if(gateway!==undefined)return gateway;const video=")
patch(C/'lib/eastern-api.ts',"aiReady:!!(a.enabled&&a.apiKey&&a.model)","aiReady:!!(a.enabled&&a.apiKey&&a.model),aiGatewayReady:!!(await this.setting('ai_gateway')).enabled")
patch(C/'lib/eastern-api.ts',"export async function handleAPI(request:Request,env:any){const api=new API(request,env);","export async function handleAPI(request:Request,env:any,executionContext?:any){const api=new API(request,env);(api as any).executionContext=executionContext;")
patch(C/'worker/index.ts',"return handleAPI(request, env);","return handleAPI(request, env, ctx);")
patch(F/'platform.js',"aiReady:d.aiReady,loaded:true","aiReady:d.aiReady,gatewayReady:!!d.aiGatewayReady,loaded:true")
patch(F/'time-bank-admin.html',"['users','settings','moderation','commerce','privacy']","['users','settings','moderation','commerce','privacy','aiGateway']")
patch(F/'time-bank-admin.html','/*__HOME_VIDEO_ADMIN__*/','/*__HOME_VIDEO_ADMIN__*/\n/*__AI_GATEWAY_ADMIN__*/')
patch(F/'build.py',"'home-video.css'","'home-video.css','ai-gateway-ui.css'")
patch(F/'build.py',"'home-video.js','i18n-ui.js'","'home-video.js','ai-gateway-ui.js','i18n-ui.js'")
for p,var in [(F/'build.py','ROOT'),(C/'prepare.py','source')]:
 old=".replace('/*__HOME_VIDEO_ADMIN__*/',("+var+"/'home-video-admin.js').read_text(encoding='utf-8'))"
 patch(p,old,old+".replace('/*__AI_GATEWAY_ADMIN__*/',("+var+"/'ai-gateway-admin.js').read_text(encoding='utf-8'))")
exports={
 'aiGatewayWallet':'SELECT balance,reserved,updated FROM ai_gateway_wallets WHERE owner=?',
 'aiGatewayGrants':'SELECT request_id,credits,created FROM ai_gateway_grants WHERE owner=?',
 'aiGatewayProviderPermissions':'SELECT provider_id,provider_binding,policy_version,global_revision,categories,revision,created,updated FROM ai_gateway_provider_consents WHERE owner=?',
 'aiGatewayRequests':'SELECT id,request_id,scene,environment,status,cancel_requested,reserve_credits,charged_credits,has_output,output_chars,usage,error_code,created,updated FROM ai_gateway_jobs WHERE owner=?',
 'aiGatewayQuotaEvents':'SELECT job_id,action,credits,rule_version,created FROM ai_gateway_quota_events WHERE owner=?',
 'aiGatewayAttempts':'SELECT job_id,provider_id,model,protocol,status,upstream_request_id,usage,cost_minor,currency,output_chars,error_code,created,updated FROM ai_gateway_attempts WHERE owner=?',
}
p=F/'backend/privacy.py';old="            'commerceInventoryEvents': ('SELECT environment,order_id,item_id,sku_id,quantity_delta,reason,created FROM commerce_inventory_events WHERE owner=?',),"
patch(p,old,old+'\n'+'\n'.join('            '+repr(k)+': ('+repr(sql)+',),' for k,sql in exports.items()))
p=C/'lib/privacy-api.ts';old="   commerceInventoryEvents:'SELECT environment,order_id,item_id,sku_id,quantity_delta,reason,created FROM commerce_inventory_events WHERE owner=?'"
patch(p,old,old+',\n'+',\n'.join('   '+k+':'+repr(sql) for k,sql in exports.items()))
for p in [F/'backend/privacy.py',C/'lib/privacy-api.ts']:
 patch(p,"'published-works', 'commerce-ledger'","'published-works', 'commerce-ledger', 'ai-request-quota-metadata'") if p.suffix=='.py' else patch(p,"'published-works','commerce-ledger'","'published-works','commerce-ledger','ai-request-quota-metadata'")
print('Integrated real SSE transport, explicit provider receipts and owner-scoped AI quota export; production quotas remain disabled.')
