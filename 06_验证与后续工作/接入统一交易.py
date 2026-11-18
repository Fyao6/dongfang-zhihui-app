"""Wire the new commerce module into the existing application without duplicating it."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
R4=ROOT/'04_研发源码/app/r4'
def patch(p,old,new):
 s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(str(p),old[:100])
 p.write_text(s.replace(old,new,1),encoding='utf-8')

# Product identity and SKU identity are intentionally different.
p=R4/'commerce-ui.js'
patch(p,"pending:coText('Awaiting payment'","unpaid:coText('Awaiting payment','待支付','待支付','དངུལ་སྤྲོད་རྒྱུ།'),pending:coText('Awaiting payment'")
patch(p,"['line1',coText('Address'","['address',coText('Address'")
patch(p,"name==='line1'?","name==='address'?")
patch(p,"${o.trackingNumber?","${(o.tracking?.trackingNumber||o.trackingNumber)?")
patch(p,'esc(o.trackingNumber)','esc(o.tracking?.trackingNumber||o.trackingNumber)')
s=p.read_text(encoding='utf-8')
if 'active.aftersaleRequest=null;closeSheet();' in s:
 p.write_text(s.replace('active.aftersaleRequest=null;closeSheet();','closeSheet();',1),encoding='utf-8')
if '--ui-only' in sys.argv:sys.exit(0)

for p in [R4/'backend/commerce.py',ROOT/'04_研发源码/app/cloud/lib/commerce-api.ts']:
 assert p.is_file(),'Backend implementation is required before activation: '+str(p)

patch(R4/'backend/server.py',"from zoneinfo import ZoneInfo, ZoneInfoNotFoundError","""from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
try:
    from commerce import Commerce, init_schema as init_commerce_schema, public_media as commerce_public_media
except ModuleNotFoundError:
    import importlib.util
    _commerce_spec = importlib.util.spec_from_file_location('eastern_commerce', Path(__file__).with_name('commerce.py'))
    _commerce_module = importlib.util.module_from_spec(_commerce_spec)
    _commerce_spec.loader.exec_module(_commerce_module)
    Commerce, init_commerce_schema = _commerce_module.Commerce, _commerce_module.init_schema
    commerce_public_media = _commerce_module.public_media""")
patch(R4/'backend/server.py','            init_analytics_schema(db)','            init_analytics_schema(db)\n            init_commerce_schema(db)')
patch(R4/'backend/server.py','        def api(self, method, path):','''        def api(self, method, path):
            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)
            if commerce_result is not None:
                return commerce_result''')
patch(R4/'backend/server.py','from commerce import Commerce, init_schema as init_commerce_schema','from commerce import Commerce, init_schema as init_commerce_schema, public_media as commerce_public_media')
patch(R4/'backend/server.py','Commerce, init_commerce_schema = _commerce_module.Commerce, _commerce_module.init_schema','Commerce, init_commerce_schema = _commerce_module.Commerce, _commerce_module.init_schema\n    commerce_public_media = _commerce_module.public_media')
patch(R4/'backend/server.py','                staff_review = False','                public = public or commerce_public_media(db, reference)\n                staff_review = False')
cloud=ROOT/'04_研发源码/app/cloud'
patch(cloud/'lib/eastern-api.ts',"import {initAnalytics,analyticsRoute} from './analytics-api';","import {initAnalytics,analyticsRoute} from './analytics-api';\nimport {initCommerce,commerceRoute,commerceMediaPublic} from './commerce-api';")
patch(cloud/'lib/eastern-api.ts',"import {initCommerce,commerceRoute,commerceMediaPublic} from './commerce-api';","import {initCommerce,commerceRoute,commerceMediaPublic} from './commerce-api';")
patch(cloud/'lib/eastern-api.ts','const published=!!await this.one(', 'const published=!!await commerceMediaPublic(this,ref)||!!await this.one(')
patch(cloud/'lib/eastern-api.ts','await initCreator(this);await initAnalytics(this);','await initCreator(this);await initAnalytics(this);await initCommerce(this);')
patch(cloud/'lib/eastern-api.ts',"async route(){const p=this.url.pathname.replace(/\\/+$/,'')||'/',m=this.method;","async route(){const p=this.url.pathname.replace(/\\/+$/,'')||'/',m=this.method;const commerce=await commerceRoute(this,p,m,fail);if(commerce!==undefined)return commerce;")
patch(R4/'community-feed.js',"['community',t('For you','推荐视频')]","['community',t('For you','推荐视频')],['commerceShop',t('Shop','商城')]")
patch(R4/'time-bank-admin.html',"dashboard:'运营概览',","dashboard:'运营概览',commerce:'商城与订单',")
patch(R4/'time-bank-admin.html',"!['users','settings','moderation'].includes(k)","!['users','settings','moderation','commerce'].includes(k)")
patch(R4/'time-bank-admin.html',"else if(nav==='analytics'){await loadAnalyticsAdmin(seq);}","else if(nav==='commerce'){await loadCommerceAdmin(seq);}\n else if(nav==='analytics'){await loadAnalyticsAdmin(seq);}")
patch(R4/'time-bank-admin.html','/*__ANALYTICS_ADMIN__*/','/*__ANALYTICS_ADMIN__*/\n/*__COMMERCE_ADMIN__*/')
patch(R4/'build.py',"'foundation-state.css','app-density.css'","'foundation-state.css','app-density.css','commerce-ui.css'")
patch(R4/'build.py',"'foundation-state.js','i18n-ui.js'","'foundation-state.js','commerce-ui.js','i18n-ui.js'")
patch(R4/'build.py',".replace('/*__ANALYTICS_ADMIN__*/',(ROOT/'analytics-admin.js').read_text(encoding='utf-8'))",".replace('/*__ANALYTICS_ADMIN__*/',(ROOT/'analytics-admin.js').read_text(encoding='utf-8')).replace('/*__COMMERCE_ADMIN__*/',(ROOT/'commerce-admin.js').read_text(encoding='utf-8'))")
patch(cloud/'prepare.py',".replace('/*__ANALYTICS_ADMIN__*/',(source/'analytics-admin.js').read_text(encoding='utf-8'))",".replace('/*__ANALYTICS_ADMIN__*/',(source/'analytics-admin.js').read_text(encoding='utf-8')).replace('/*__COMMERCE_ADMIN__*/',(source/'commerce-admin.js').read_text(encoding='utf-8'))")
patch(ROOT/'06_验证与后续工作/全量回归.cjs',"assert.equal(await page.locator('.community-tabs button').count(),4)","assert.equal(await page.locator('.community-tabs button').count(),5);assert.deepEqual(await page.locator('.community-tabs button').evaluateAll(es=>es.map(e=>e.dataset.to)),['friends','communityInbox','communityTeachers','community','commerceShop'])")
extra=R4/'i18n-extra.json'
import json
data=json.loads(extra.read_text(encoding='utf-8'))
data['商城']={'en':'Shop','bo':'ཚོང་ཁང་།'}
extra.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Activated the shared commerce API, shop, order console and retained all four community entries.')
