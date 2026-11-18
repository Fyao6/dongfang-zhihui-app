"""Root-owned card integration plan. Default is a read-only dry run; --apply is for the later module gate."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
files={};changes=[]
def once(name,marker,old,new):
    p=ROOT/name
    text=files.get(p,p.read_text(encoding='utf-8-sig'))
    if marker in text:return
    if text.count(old)!=1:raise RuntimeError('Integration anchor is not unique: '+name+' / '+marker)
    files[p]=text.replace(old,new,1);changes.append({'file':name,'marker':marker})
server='04_研发源码/app/r4/backend/server.py';privacy='04_研发源码/app/r4/backend/privacy.py';cloud='04_研发源码/app/cloud/lib/eastern-api.ts';cp='04_研发源码/app/cloud/lib/privacy-api.ts'
imports="""# card-service-integration:v1
try:
    from card_service import CardService, init_schema as init_card_service_schema, media_allowed as card_media_allowed
except ModuleNotFoundError:
    import importlib.util as _card_import
    _card_spec=_card_import.spec_from_file_location('eastern_card_service',Path(__file__).with_name('card_service.py'))
    _card_module=_card_import.module_from_spec(_card_spec);_card_spec.loader.exec_module(_card_module)
    CardService,init_card_service_schema,card_media_allowed=_card_module.CardService,_card_module.init_schema,_card_module.media_allowed
"""
once(server,'# card-service-integration:v1','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError\n','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError\n'+imports)
once(server,'            init_card_service_schema(db)','            init_ai_gateway_schema(db)','            init_ai_gateway_schema(db)\n            init_card_service_schema(db)')
once(server,'            card_result = CardService','            gateway_result = AIGateway',"            card_result = CardService(store, self, ApiError, rate_limit).route(method, path)\n            if card_result is not None:\n                return card_result\n            gateway_result = AIGateway")
once(server,'cardServiceReady=','membershipServiceReady=bool(store.setting(\'membership_lifecycle\').get(\'sandboxEnabled\'))',"membershipServiceReady=bool(store.setting('membership_lifecycle').get('sandboxEnabled')), cardServiceReady=bool(store.setting('card_service').get('enabled'))")
once(server,'public = public or card_media_allowed','                public = public or commerce_public_media(db, reference)',"                public = public or commerce_public_media(db, reference)\n                public = public or card_media_allowed(db, reference, self.user['id'] if self.user else None)")
private_imports="""# card-service-privacy:v1
try:
    from card_service import privacy_export as card_privacy_export, privacy_delete_records as card_privacy_delete_records
except ModuleNotFoundError:
    import importlib.util as _card_privacy_import
    from pathlib import Path as _CardPrivacyPath
    _card_privacy_spec=_card_privacy_import.spec_from_file_location('eastern_card_privacy',_CardPrivacyPath(__file__).with_name('card_service.py'))
    _card_privacy_module=_card_privacy_import.module_from_spec(_card_privacy_spec);_card_privacy_spec.loader.exec_module(_card_privacy_module)
    card_privacy_export,card_privacy_delete_records=_card_privacy_module.privacy_export,_card_privacy_module.privacy_delete_records
"""
once(privacy,'# card-service-privacy:v1','from uuid import uuid4\n','from uuid import uuid4\n'+private_imports)
once(privacy,'result.update(card_privacy_export',"            self.store.audit(db, self.uid, 'privacy.export',", "            result.update(card_privacy_export(db, self.uid))\n            self.store.audit(db, self.uid, 'privacy.export',")
once(privacy,"deleted.update(card_privacy_delete_records", "                deleted['measurements'] = db.execute('DELETE FROM measurements WHERE connection_id IN (SELECT id FROM devices WHERE owner=?)', (self.uid,)).rowcount", "                deleted['measurements'] = db.execute('DELETE FROM measurements WHERE connection_id IN (SELECT id FROM devices WHERE owner=?)', (self.uid,)).rowcount\n                deleted.update(card_privacy_delete_records(db, self.uid)['deletedCounts'])")
once(privacy,"'delete-records': ('chart', 'wellbeing', 'card')", "'delete-records': ('chart', 'wellbeing')", "'delete-records': ('chart', 'wellbeing', 'card')")
once(privacy,"'minimal-daily-card-quota'", "'ai-request-quota-metadata'", "'ai-request-quota-metadata', 'minimal-daily-card-quota', 'card-timezone-preferences', 'card-record-erasure-epoch'")
once(privacy,"'cardQuotaRetentionDays'", "'financeRetentionDays': cfg['retention']['financeDays']", "'financeRetentionDays': cfg['retention']['financeDays'], 'cardQuotaRetentionDays': None, 'cardQuotaRetentionNotice': '仅保留最小防重额度、时区与删除代际；不保留卡义或感受，期限待确认。'")
once(cloud,"from './card-service'", "import {initAIGateway,aiGatewayRoute} from './ai-gateway';", "import {initAIGateway,aiGatewayRoute} from './ai-gateway';\nimport {initCardService,cardServiceRoute,cardMediaAllowed} from './card-service';")
once(cloud,'await initCardService(this);','await initAIGateway(this);','await initAIGateway(this);await initCardService(this);')
once(cloud,'const cards=await cardServiceRoute',"const gateway=await aiGatewayRoute(this,p,m,fail);", "const cards=await cardServiceRoute(this,p,m,fail);if(cards!==undefined)return cards;const gateway=await aiGatewayRoute(this,p,m,fail);")
once(cloud,'cardServiceReady:',"membershipServiceReady:!!(await this.setting('membership_lifecycle')).sandboxEnabled", "membershipServiceReady:!!(await this.setting('membership_lifecycle')).sandboxEnabled,cardServiceReady:!!(await this.setting('card_service')).enabled")
once(cloud,'const published=!!await cardMediaAllowed', 'const published=!!await commerceMediaPublic(this,ref)', 'const published=!!await cardMediaAllowed(this,ref,this.user?.id)||!!await commerceMediaPublic(this,ref)')
once(cp,'CARD_PRIVACY_QUERIES,cardPrivacyDeletionStatements', "import {globalBinding}", "import {globalBinding}") if False else None
# This file's first import varies by the earlier bridge gate; prepend our independent import once.
p=ROOT/cp;text=files.get(p,p.read_text(encoding='utf-8-sig'))
if 'CARD_PRIVACY_QUERIES,cardPrivacyDeletionStatements' not in text:
    files[p]="import {CARD_PRIVACY_QUERIES,cardPrivacyDeletionStatements,CARD_PRIVACY_DELETE_COUNTS_SQL} from './card-service';\n"+text;changes.append({'file':cp,'marker':'card-service privacy import'})
once(cp,'...CARD_PRIVACY_QUERIES,','const queries:Record<string,string>={','const queries:Record<string,string>={...CARD_PRIVACY_QUERIES,')
once(cp,"'delete-records':['chart','wellbeing','card']", "'delete-records':['chart','wellbeing']", "'delete-records':['chart','wellbeing','card']")
once(cp,"'minimal-daily-card-quota'", "'ai-request-quota-metadata'", "'ai-request-quota-metadata','minimal-daily-card-quota','card-timezone-preferences','card-record-erasure-epoch'")
once(cp,'cardQuotaRetentionDays:', 'financeRetentionDays:cfg.retention.financeDays', "financeRetentionDays:cfg.retention.financeDays,cardQuotaRetentionDays:null,cardQuotaRetentionNotice:'仅保留最小防重额度、时区与删除代际；不保留卡义或感受，期限待确认。'")
once(cp,'actions.push(...cardPrivacyDeletionStatements', "   if(kind==='close-account'){const p=await prefs(a,uid);", "   if(kind==='delete-records')actions.push(...cardPrivacyDeletionStatements(a,uid));\n   if(kind==='close-account'){const p=await prefs(a,uid);")
once(cp,'// card-service-delete-counts:v1', '   // A unique request row and the destructive statements form one atomic batch.', "   // card-service-delete-counts:v1: merge counts in the same pre-deletion atomic snapshot.\n   if(kind==='delete-records'){detailSQL=\"json_patch(\"+detailSQL+\",json_object('local',json_object('deletedCounts',\"+CARD_PRIVACY_DELETE_COUNTS_SQL+\")))\";detailArgs.push(uid,uid,uid,uid);}\n   // A unique request row and the destructive statements form one atomic batch.")
platform='04_研发源码/app/r4/platform.js'
once(platform,'cardServiceReady:!!d.cardServiceReady', 'gatewayReady:!!d.aiGatewayReady,', 'gatewayReady:!!d.aiGatewayReady,cardServiceReady:!!d.cardServiceReady,')
admin='04_研发源码/app/r4/time-bank-admin.html'
once(admin,"'cardService'", "'aiGateway','memberSubscriptions'", "'aiGateway','memberSubscriptions','cardService'")
once(admin,'/*__CARD_SERVICE_ADMIN__*/','/*__MEMBERSHIP_ADMIN__*/','/*__MEMBERSHIP_ADMIN__*/\n/*__CARD_SERVICE_ADMIN__*/')
build='04_研发源码/app/r4/build.py';prepare='04_研发源码/app/cloud/prepare.py'
once(build,"'card-service.css'", "'membership-lifecycle-ui.css'", "'membership-lifecycle-ui.css','card-service.css'")
once(build,"'card-service-ui.js'", "'i18n-ui.js'", "'card-service-ui.js','i18n-ui.js'")
for name,base in ((build,'ROOT'),(prepare,'source')):
    old=".replace('/*__MEMBERSHIP_ADMIN__*/',("+base+"/'membership-lifecycle-admin.js').read_text(encoding='utf-8'))"
    once(name,".replace('/*__CARD_SERVICE_ADMIN__*/'",old,old+".replace('/*__CARD_SERVICE_ADMIN__*/',("+base+"/'card-service-admin.js').read_text(encoding='utf-8'))")
once(build,'# card-service-admin-css:v1','creator_source=',"# card-service-admin-css:v1\nadmin_source=admin_source.replace('</style>',(ROOT/'card-service.css').read_text(encoding='utf-8')+'</style>',1)\ncreator_source=")
once(prepare,'# card-service-admin-css:v1',"(generated/'creator.html').write_text", "# card-service-admin-css:v1\nadmin=admin.replace('</style>',(source/'card-service.css').read_text(encoding='utf-8')+'</style>',1)\n(generated/'creator.html').write_text")
# Precompute and parse all edits before any optional write. Re-running must produce zero replacements.
for p,text in files.items():
    if p.suffix=='.py':ast.parse(text)
if args.apply:
    for p,text in files.items():p.write_text(text,encoding='utf8')
report={'mode':'apply' if args.apply else 'dry-run','applied':args.apply,'publicIntegrationExecutedByThisDryRun':args.apply,'files':[{ 'path':str(p.relative_to(ROOT)),'beforeSha256':hashlib.sha256(p.read_bytes()).hexdigest() if not args.apply else None,'plannedSha256':hashlib.sha256(text.encode()).hexdigest()} for p,text in files.items()],'changes':changes,'buildExecuted':False,'databaseAccessed':False}
output=Path(__file__).with_suffix('.json');runs=json.loads(output.read_text(encoding='utf8')).get('runs',[]) if output.exists() else [];runs.append(report);output.write_text(json.dumps({'latest':report,'runs':runs},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'mode':report['mode'],'files':len(files),'changes':len(changes),'buildExecuted':False,'databaseAccessed':False}))
