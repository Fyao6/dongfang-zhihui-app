"""Wire homepage video into current content, revision and media permissions."""
from pathlib import Path
R=Path(__file__).resolve().parent.parent;A=R/'04_研发源码/app';F=A/'r4';C=A/'cloud'
def patch(p,old,new):
 s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(str(p),old[:120])
 p.write_text(s.replace(old,new,1),encoding='utf-8')
patch(F/'backend/server.py','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError',"""from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
try:
    from video import Video, validate_video_item, authorize_video_media
except ModuleNotFoundError:
    import importlib.util
    _video_spec = importlib.util.spec_from_file_location('eastern_video', Path(__file__).with_name('video.py'))
    _video_module = importlib.util.module_from_spec(_video_spec)
    _video_spec.loader.exec_module(_video_module)
    Video, validate_video_item, authorize_video_media = _video_module.Video, _video_module.validate_video_item, _video_module.authorize_video_media"""
)
patch(F/'backend/server.py','        def api(self, method, path):','''        def api(self, method, path):
            video_result = Video(store, self, ApiError, rate_limit).route(method, path)
            if video_result is not None:
                return video_result''')
patch(F/'backend/server.py',"                    if status not in ('draft', 'published', 'archived'):\n                        raise ValueError('无效发布状态。')\n                    old = db.execute('SELECT * FROM contents WHERE kind=? AND id=?', (kind, item_id)).fetchone()","                    if status not in ('draft', 'published', 'archived'):\n                        raise ValueError('无效发布状态。')\n                    if kind == 'quotes':\n                        item = validate_video_item(item, status, ApiError)\n                        authorize_video_media(db, item, uid, ApiError)\n                    old = db.execute('SELECT * FROM contents WHERE kind=? AND id=?', (kind, item_id)).fetchone()")
patch(F/'backend/server.py',"                    current = db.execute('SELECT * FROM contents WHERE kind=? AND id=?', (snap['kind'], snap['id'])).fetchone()","""                    if snap['kind'] == 'quotes':
                        restored_video = validate_video_item(json.loads(snap['data']), snap['status'], ApiError)
                        authorize_video_media(db, restored_video, uid, ApiError)
                        snap['data'] = dump(restored_video)
                    current = db.execute('SELECT * FROM contents WHERE kind=? AND id=?', (snap['kind'], snap['id'])).fetchone()"""
)
patch(C/'lib/eastern-api.ts',"import seed from '../generated/seed.json';","import {videoRoute,validateVideoItem,authorizeVideoMedia} from './video-api';\nimport seed from '../generated/seed.json';")
patch(C/'lib/eastern-api.ts',"m=this.method;const privacy=","m=this.method;const video=await videoRoute(this,p,m,fail);if(video!==undefined)return video;const privacy=")
patch(C/'lib/eastern-api.ts',"const position=Math.max(-10000,Math.min(10000,Math.trunc(Number(d.position)||0))),old=", "if(kind==='quotes'){Object.assign(item,validateVideoItem(item,status,fail));await authorizeVideoMedia(this,item,fail);}const position=Math.max(-10000,Math.min(10000,Math.trunc(Number(d.position)||0))),old=")
patch(C/'lib/eastern-api.ts',"const current=await this.one('SELECT * FROM contents WHERE kind=? AND id=?',snap.kind,snap.id),st=[];","if(snap.kind==='quotes'){const restoredVideo=validateVideoItem(JSON.parse(snap.data),snap.status,fail);await authorizeVideoMedia(this,restoredVideo,fail);snap.data=dump(restoredVideo);}const current=await this.one('SELECT * FROM contents WHERE kind=? AND id=?',snap.kind,snap.id),st=[];")
patch(F/'time-bank-admin.html','/*__PRIVACY_ADMIN__*/','/*__PRIVACY_ADMIN__*/\n/*__HOME_VIDEO_ADMIN__*/')
patch(F/'build.py',"'privacy-center.css'","'privacy-center.css','home-video.css'")
patch(F/'build.py',"'privacy-ai-client.js','i18n-ui.js'","'privacy-ai-client.js','home-video.js','i18n-ui.js'")
for p,var in [(F/'build.py','ROOT'),(C/'prepare.py','source')]:
 old=".replace('/*__PRIVACY_ADMIN__*/',("+var+"/'privacy-admin.js').read_text(encoding='utf-8'))"
 patch(p,old,old+".replace('/*__HOME_VIDEO_ADMIN__*/',("+var+"/'home-video-admin.js').read_text(encoding='utf-8'))")
print('Homepage video shares the existing quotes/revisions and enforces the same validation on generic writes and rollbacks.')
