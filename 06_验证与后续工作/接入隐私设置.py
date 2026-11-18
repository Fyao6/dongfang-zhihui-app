"""Integrate the reviewed privacy controls into the existing entry points."""
from pathlib import Path
R=Path(__file__).resolve().parent.parent
A=R/'04_研发源码/app';F=A/'r4';C=A/'cloud'
def patch(p,old,new):
 s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(str(p),old[:120])
 p.write_text(s.replace(old,new,1),encoding='utf-8')

patch(F/'backend/server.py','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError',"""from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
try:
    from privacy import Privacy, init_schema as init_privacy_schema, authorize_ai as privacy_authorize_ai, save_conversation as privacy_save_conversation
except ModuleNotFoundError:
    import importlib.util
    _privacy_spec = importlib.util.spec_from_file_location('eastern_privacy', Path(__file__).with_name('privacy.py'))
    _privacy_module = importlib.util.module_from_spec(_privacy_spec)
    _privacy_spec.loader.exec_module(_privacy_module)
    Privacy, init_privacy_schema = _privacy_module.Privacy, _privacy_module.init_schema
    privacy_authorize_ai, privacy_save_conversation = _privacy_module.authorize_ai, _privacy_module.save_conversation"""
)
patch(F/'backend/server.py','            init_commerce_schema(db)','            init_commerce_schema(db)\n            init_privacy_schema(db)')
patch(F/'backend/server.py','        def api(self, method, path):','''        def api(self, method, path):
            privacy_result = Privacy(store, self, ApiError, rate_limit).route(method, path)
            if privacy_result is not None:
                return privacy_result''')
patch(F/'backend/server.py',"            inputs = []\n            for message in messages:","            context = privacy_authorize_ai(store, self.user, data, ApiError, provider_id=ai.get('providerId'), ai_config=ai)\n            inputs = []\n            for message in messages:")
patch(F/'backend/server.py',"            context = data.get('context')\n            if context:","            # Only the approved minimal context may reach the configured provider.\n            if context:")
patch(F/'backend/server.py',"                return {'text': answer}","""                fresh = Privacy(store, self, ApiError, rate_limit).response()
                if not fresh['policyAcknowledged'] or fresh['consentEpoch'] != messages[-1]['privacy']['consentEpoch']:
                    raise ApiError(409, '授权已变更，本次回复已丢弃。')
                reply_tag = {**messages[-1]['privacy'], 'source': 'assistant'}
                privacy_save_conversation(store, self.user['id'], messages + [{'role': 'assistant', 'content': answer, 'privacy': reply_tag}])
                return {'text': answer}"""
)
patch(F/'backend/server.py',"if k in ('enabled', 'model', 'prompt', 'knowledge')","if k in ('enabled', 'model', 'prompt', 'knowledge', 'providerId', 'processingRegions', 'privacyPolicyVersion')")
patch(F/'backend/server.py',"                    text(old_ai.get('knowledge', ''), 20000)","""                    text(old_ai.get('knowledge', ''), 20000)
                    provider_id = text(old_ai.get('providerId', ''), 80)
                    if provider_id and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', provider_id):
                        raise ValueError('AI供应商编号格式不正确。')
                    regions = old_ai.get('processingRegions', [])
                    if not isinstance(regions, list) or len(regions) > 12 or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 80 for v in regions):
                        raise ValueError('AI处理地区须为已确认的地区名称数组。')
                    text(old_ai.get('privacyPolicyVersion', ''), 80)"""
)
patch(C/'lib/eastern-api.ts',"import seed from '../generated/seed.json';","import {initPrivacy,privacyRoute,authorizeAI,savePrivacyConversation} from './privacy-api';\nimport seed from '../generated/seed.json';")
patch(C/'lib/eastern-api.ts','await initCommerce(this);','await initCommerce(this);await initPrivacy(this);')
patch(C/'lib/eastern-api.ts',"m=this.method;const commerce=", "m=this.method;const privacy=await privacyRoute(this,p,m,fail);if(privacy!==undefined)return privacy;const commerce=")
patch(C/'lib/eastern-api.ts',"const input=d.messages.map", "const context=await authorizeAI(this,d,fail,a.providerId,a);const input=d.messages.map")
patch(C/'lib/eastern-api.ts',"if(d.context)instructions+=", "if(context)instructions+=")
patch(C/'lib/eastern-api.ts',"text(dump(d.context),6000)", "text(dump(context),6000)")
patch(C/'lib/eastern-api.ts',"return {text:answer};}","const fresh:any=await privacyRoute(this,'/api/privacy/preferences','GET',fail);if(!fresh.policyAcknowledged||fresh.consentEpoch!==d.messages.at(-1).privacy.consentEpoch)fail(409,'授权已变更，本次回复已丢弃。');await savePrivacyConversation(this,this.user.id,[...d.messages,{role:'assistant',content:answer,privacy:{...d.messages.at(-1).privacy,source:'assistant'}}]);return {text:answer};}")
patch(C/'lib/eastern-api.ts',"['enabled','model','prompt','knowledge']","['enabled','model','prompt','knowledge','providerId','processingRegions','privacyPolicyVersion']")
patch(C/'lib/eastern-api.ts',"text(old.knowledge||'',20000)","text(old.knowledge||'',20000);text(old.providerId||'',80);if(old.providerId&&!/^[A-Za-z0-9_-]{1,80}$/.test(old.providerId))fail(400,'AI供应商编号格式不正确。');if(!Array.isArray(old.processingRegions||[])||(old.processingRegions||[]).length>12||(old.processingRegions||[]).some((v:any)=>typeof v!=='string'||!v.trim()||v.length>80))fail(400,'AI处理地区须为已确认的地区名称数组。');text(old.privacyPolicyVersion||'',80)")
patch(F/'profile.js',"${profileMenu('info',t('About my records','关于我的记录'),'profileData')}","${profileMenu('settings',privacyTitle(),'privacyCenter')}${profileMenu('info',t('About my records','关于我的记录'),'profileData')}")
patch(F/'service-social.js',"else if(a==='ss-context-clear'){state.ssAiContext=null;render(false);}","else if(a==='ss-context-clear'){state.ssAiContext=null;px.retry=null;render(false);}")
patch(F/'service-social.js',"else if(a==='ss-ai-clear-confirm'){if(!psCommit(()=>{state.support.ai=[];}))return;state.ssAiContext=null;closeSheet();render();}","else if(a==='ss-ai-clear-confirm'){if(!privacyClearLocal('conversations',psToken()))return;++px.privacyRun;px.busy=false;px.retry=null;state.ssAiContext=null;closeSheet();render();}")
patch(F/'platform.js',"else if(a==='px-ai-retry'){const last=state.support.ai.filter(x=>x.role==='user').at(-1);if(last)pxAsk(last.text,true);}","else if(a==='px-ai-retry'){if(px.retry)pxAsk(px.retry.text,true);}")
patch(F/'platform.js',"pxAsk(pxText('我今天抽到“','Today’s card is “')+ewI18n.content(card,\"\",state.lang)+'”。'+ewI18n.content(card,\"line\",state.lang));","pxAsk(prText('Please explain my selected card.','请解释本次选定的卡片。','請解釋本次選定的卡片。','བདམས་པའི་ཤོག་བྱང་གསལ་བཤད་བྱོས།'),false,{category:'card',fields:{cardId:card.id,meaning:ewI18n.content(card,\"line\",state.lang)}},'report');")
patch(F/'time-bank-admin.html',"commerce:'商城与订单',","commerce:'商城与订单',privacy:'隐私配置与处理申请',")
patch(F/'time-bank-admin.html',"['users','settings','moderation','commerce']","['users','settings','moderation','commerce','privacy']")
patch(F/'time-bank-admin.html',"else if(nav==='commerce'){await loadCommerceAdmin(seq);}","else if(nav==='privacy'){await loadPrivacyAdmin(seq);}\n else if(nav==='commerce'){await loadCommerceAdmin(seq);}")
patch(F/'time-bank-admin.html','/*__COMMERCE_ADMIN__*/','/*__COMMERCE_ADMIN__*/\n/*__PRIVACY_ADMIN__*/')
patch(F/'time-bank-admin.html','<label>API密钥<input', '<label>实际供应商ID<input name="providerId" maxlength="80" value="${esc(a.providerId||\'\')}" placeholder="与隐私接收方ID一致"></label><label>实际处理地区（逗号分隔）<input name="processingRegions" value="${esc((a.processingRegions||[]).join(\',\'))}"></label><label>隐私政策版本<input name="privacyPolicyVersion" maxlength="80" value="${esc(a.privacyPolicyVersion||\'\')}"></label><label>API密钥<input')
patch(F/'time-bank-admin.html',"knowledge:values.knowledge},theme:","knowledge:values.knowledge,providerId:values.providerId,processingRegions:values.processingRegions.split(',').map(x=>x.trim()).filter(Boolean),privacyPolicyVersion:values.privacyPolicyVersion},theme:")
patch(F/'build.py',"'commerce-ui.css'","'commerce-ui.css','privacy-center.css'")
patch(F/'build.py',"'commerce-ui.js','i18n-ui.js'","'commerce-ui.js','privacy-center.js','privacy-ai-client.js','i18n-ui.js'")
for p,variable in [(F/'build.py','ROOT'),(C/'prepare.py','source')]:
 old=".replace('/*__COMMERCE_ADMIN__*/',("+variable+"/'commerce-admin.js').read_text(encoding='utf-8'))"
 new=old+".replace('/*__PRIVACY_ADMIN__*/',("+variable+"/'privacy-admin.js').read_text(encoding='utf-8'))"
 patch(p,old,new)

# Keep the existing Responses parsing unit independent of the separately tested privacy gate.
p=R/'06_验证与后续工作/后台单元回归.py'
patch(p,"with patch.object(app, 'urlopen', return_value=Response()) as network:","with patch.object(app, 'urlopen', return_value=Response()) as network, patch.object(app, 'privacy_authorize_ai', return_value=None), patch.object(app, 'privacy_save_conversation', return_value=False), patch.object(app, 'Privacy') as gate:\n            gate.return_value.response.return_value = {'policyAcknowledged': True, 'consentEpoch': 'unit-receipt'}")
patch(p,"'content': '你好'}]}","'content': '你好', 'privacy': {'consentEpoch': 'unit-receipt'}}]}")
print('Integrated current-provider authorization, minimal AI payloads and real privacy controls into existing app.')
