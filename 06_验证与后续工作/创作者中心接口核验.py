"""Real local HTTP verification in a disposable database; never writes production."""
from pathlib import Path
import sys,json,threading,http.cookiejar,time,base64
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from datetime import datetime,timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import server,creator
db_path=ROOT/'06_验证与后续工作/创作者专项隔离.sqlite3'
assert not db_path.exists(), 'Existing test database must be reviewed before reuse'
store=server.Store(db_path)
httpd=ThreadingHTTPServer(('127.0.0.1',0),server.make_handler(store,ROOT/'03_当前APP'))
threading.Thread(target=httpd.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(httpd.server_port)
checks=[]
class Client:
 def __init__(self):self.opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,method,path,data=None,status=200,headers=None):
  body=data if isinstance(data,bytes) else json.dumps(data).encode() if data is not None else None
  try:
   with self.opener.open(Request(base+path,data=body,method=method,headers=headers or {'Content-Type':'application/json'}),timeout=30) as r:
    code=r.status;payload=r.read();result=json.loads(payload) if 'json' in r.headers.get('Content-Type','') else payload
  except HTTPError as e:code=e.code;result=json.loads(e.read())
  assert code==status,(method,path,code,status,result)
  return result
def checked(name):checks.append(name);print('PASS',name,flush=True)
admin,alice,bob,reader,reviewer,anon=[Client() for _ in range(6)]
password='local-creator-test-only'
def register(c,name):return c.req('POST','/api/auth/register',dict(username=name,password=password,name=name))['user']['id']
def latest(c,wid):return next(w for w in c.req('GET','/api/creator/works')['items'] if w['id']==wid)
try:
 admin_id=admin.req('POST','/api/auth/setup',dict(username='creator_admin',password=password,name='管理员'))['user']['id']
 aid,bid,rid,reviewer_id=[register(c,n) for c,n in [(alice,'creator_alice'),(bob,'creator_bob'),(reader,'creator_reader'),(reviewer,'creator_review')]]
 assert anon.req('GET','/api/creator/me')==dict(user=None,profile=None,eligible=False)
 anon.req('GET','/api/creator/works',status=401)
 alice.req('GET','/api/creator/works',status=403)
 alice.req('POST','/api/creator/apply',dict(displayName='清明老师',bio='真实测试简介',avatarUrl=''))
 bob.req('POST','/api/creator/apply',dict(displayName='另一位老师',bio='独立账号',avatarUrl=''))
 alice.req('PATCH','/api/admin/creators/'+aid,dict(status='approved'),status=403)
 admin.req('PATCH','/api/admin/creators/'+aid,dict(status='approved',teacherId='qinghe'),status=400) if False else None
 admin.req('PATCH','/api/admin/creators/'+aid,dict(status='approved',reason='已核验资质'))
 admin.req('PATCH','/api/admin/creators/'+bid,dict(status='approved',reason='已核验资质'))
 assert alice.req('GET','/api/creator/me')['eligible']
 alice.req('GET','/api/admin/users',status=403)
 profile=alice.req('GET','/api/creator/me')['profile']
 admin.req('PATCH','/api/admin/creators/'+bid,dict(status='approved',teacherId=profile['teacherId']),status=409)
 checked('申请、批准、老师角色、创作者与总后台权限隔离及老师唯一绑定')
 draft=dict(type='article',title='练习中的觉察',body='从舒适的呼吸开始。',theme='healing',format='article',categoryIds=[],sections=[],duration=0,mediaUrl='',coverUrl='')
 w=alice.req('POST','/api/creator/works',draft)['item'];wid=w['id']
 assert bob.req('GET','/api/creator/works')['items']==[]
 bob.req('PATCH','/api/creator/works/'+wid,dict(draft,version=w['version']),status=404)
 bob.req('GET','/api/creator/works/'+wid+'/reviews',status=404)
 alice.req('PATCH','/api/creator/works/'+wid,dict(draft,version=0),status=409)
 alice.req('POST','/api/creator/works',dict(draft,mediaUrl='https://example.com/mutable.mp4'),status=400)
 checked('作品按账号隔离、版本冲突及外部可变媒体拒绝')
 w=alice.req('POST','/api/creator/works/'+wid+'/submit',dict(version=w['version']))['item']
 assert w['status']=='manual_review' and 'AI' in w['reason']
 alice.req('PATCH','/api/creator/works/'+wid,dict(draft,version=w['version']),status=409)
 anon.req('POST','/api/creator-events',dict(workId=wid,event='view',sessionId='session-0001'),status=404)
 admin.req('PATCH','/api/admin/users/'+reviewer_id,dict(role='reviewer'))
 reviewer.req('PUT','/api/admin/moderation-settings',dict(enabled=False,autoApprove=False,rules='',knowledge=''),status=403)
 details=reviewer.req('GET','/api/admin/creator-reviews/'+wid)
 assert details['reviews'] and details['reviews'][0]['stage']=='ai'
 reviewer.req('POST','/api/admin/creator-reviews/'+wid,dict(decision='approve',reason='',version=w['version']),status=400)
 w=reviewer.req('POST','/api/admin/creator-reviews/'+wid,dict(decision='approve',reason='人工核对通过',version=w['version']))['item']
 assert w['status']=='published'
 assert next(x for x in anon.req('GET','/api/community/posts')['items'] if x['id']==wid)['creatorId']==aid
 public=anon.req('GET','/api/creators/'+aid); assert 'reason' not in public['works'][0]
 alice.req('PATCH','/api/community/posts/'+wid,dict(title='绕过审核',body='绕过',status='pending'),status=409)
 admin.req('PATCH','/api/admin/posts/'+wid,dict(status='published'),status=409)
 checked('无AI凭据转人工、复核权限与理由、真实发布、旧入口防绕过')
 reader.req('POST','/api/creators/'+aid+'/follow',dict(active=True));reader.req('POST','/api/creators/'+aid+'/follow',dict(active=True))
 alice.req('POST','/api/creators/'+aid+'/follow',dict(active=True),status=400)
 for _ in range(2):reader.req('POST','/api/creator-events',dict(workId=wid,event='view',sessionId='session-0001'))
 for _ in range(2):reader.req('POST','/api/creator-actions',dict(workId=wid,action='like',active=True))
 alice.req('POST','/api/creator-actions',dict(workId=wid,action='like',active=True),status=400)
 reader.req('POST','/api/creator-events',dict(workId=wid,event='learn',sessionId='session-0001'),status=400)
 stats=alice.req('GET','/api/creator/analytics?days=7')
 assert stats['totals']['followers']==1 and stats['totals']['views']==1 and stats['totals']['likes']==1 and len(stats['daily'])==7
 assert bob.req('GET','/api/creator/analytics')['totals']['views']==0
 assert not any('visitor' in row for row in stats['daily'])
 checked('真实关注、互动和访问去重、本人排除及私有聚合数据')
 w=alice.req('PATCH','/api/creator/works/'+wid,dict(draft,title='修订版本',version=w['version']))['item']
 assert w['status']=='draft' and not any(x['id']==wid for x in anon.req('GET','/api/community/posts')['items'])
 w=alice.req('POST','/api/creator/works/'+wid+'/submit',dict(version=w['version']))['item']
 w=reviewer.req('POST','/api/admin/creator-reviews/'+wid,dict(decision='reject',reason='请补充出处',version=w['version']))['item']
 w=alice.req('POST','/api/creator/works/'+wid+'/appeal',dict(reason='已附来源，请复核',version=w['version']))['item']
 assert w['status']=='manual_review'
 w=alice.req('POST','/api/creator/works/'+wid+'/withdraw',dict(version=w['version']))['item']
 reviewer.req('POST','/api/admin/creator-reviews/'+wid,dict(decision='approve',reason='过期审核',version=w['version']-1),status=409)
 checked('编辑即下架、驳回申诉、撤回与过期人工审核防护')
 c=alice.req('POST','/api/creator/works',dict(draft,type='course',title='觉察课程',body='课程正文',duration=60))['item']
 c=alice.req('POST','/api/creator/works/'+c['id']+'/submit',dict(version=c['version']))['item']
 c=admin.req('POST','/api/admin/creator-reviews/'+c['id'],dict(decision='approve',reason='课程内容审核通过',version=c['version']))['item']
 course=next(x for x in anon.req('GET','/api/public')['content']['courses'] if x['id']==c['id'])
 assert course['creatorId']==aid and course['access']=='public' and course['summaryZh']=='课程正文'
 admin.req('POST','/api/admin/content/courses',dict(item=course,status='published'),status=409)
 reader.req('POST','/api/creator-events',dict(workId=c['id'],event='play',sessionId='session-course'))
 reader.req('POST','/api/creator-events',dict(workId=c['id'],event='watch',sessionId='session-course',seconds=999999))
 reader.req('POST','/api/creator-events',dict(workId=c['id'],event='complete',sessionId='session-course'))
 reader.req('POST','/api/creator-events',dict(workId=c['id'],event='learn',sessionId='session-course'))
 data=alice.req('GET','/api/creator/analytics')['totals'];assert data['watchSeconds']<5 and data['completions']==0 and data['learners']==1
 today=datetime.now().strftime('%Y-%m-%d')
 rid=reader.req('POST','/api/service-requests',dict(teacherId=profile['teacherId'],date=today,body='希望预约一次交流'))['id']
 assert any(x['id']==rid for x in alice.req('GET','/api/creator/consultations')['items'])
 bob.req('PATCH','/api/creator/consultations/'+rid,dict(status='accepted'),status=404)
 alice.req('PATCH','/api/creator/consultations/'+rid,dict(status='accepted'))
 alice.req('PATCH','/api/creator/consultations/'+rid,dict(status='closed'))
 checked('课程真实发布、学习人数、观看时长约束、完播防虚增和咨询归属')
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZQAAAABJRU5ErkJggg==')
 cover=alice.req('POST','/api/media',png,headers={'Content-Type':'image/png','X-Filename':'cover.png'})['url']
 private=reader.req('POST','/api/media',png,headers={'Content-Type':'image/png','X-Filename':'private.png'})['url']
 alice.req('POST','/api/creator/works',dict(draft,coverUrl=private),status=403)
 video=alice.req('POST','/api/media',b'\x00\x00\x00\x14ftypisom\x00\x00\x00\x00isom',headers={'Content-Type':'video/mp4','X-Filename':'test.mp4'})['url']
 v=alice.req('POST','/api/creator/works',dict(draft,type='video',format='video',mediaUrl=video,coverUrl=cover,duration=20))['item']
 v=alice.req('POST','/api/creator/works/'+v['id']+'/submit',dict(version=v['version']))['item']
 assert v['status']=='manual_review'
 v=admin.req('POST','/api/admin/creator-reviews/'+v['id'],dict(decision='approve',reason='隔离素材通过',version=v['version']))['item']
 assert anon.req('GET',cover)==png
 anon.req('GET',video)
 v=alice.req('POST','/api/creator/works/'+v['id']+'/withdraw',dict(version=v['version']))['item']
 anon.req('GET',cover,status=403);anon.req('GET',video,status=403)
 alice.req('PATCH','/api/creator/profile',dict(displayName='清明老师',bio='新头像',avatarUrl=cover));assert anon.req('GET',cover)==png
 x=alice.req('POST','/api/creator/works',dict(draft,type='course',body='仅提及私有地址 '+private))['item']
 x=alice.req('POST','/api/creator/works/'+x['id']+'/submit',dict(version=x['version']))['item']
 admin.req('POST','/api/admin/creator-reviews/'+x['id'],dict(decision='approve',reason='正文审核',version=x['version']))
 anon.req('GET',private,status=403)
 checked('发布封面与头像可见、撤回媒体失效、跨账号素材引用和正文URL提权防护')
 cfg=admin.req('PUT','/api/admin/moderation-settings',dict(enabled=True,autoApprove=True,rules='允许介绍温和的呼吸觉察。禁止虚假治疗承诺。',knowledge='本平台关注日常练习与成长。'))
 with store.connect() as db:
  ai=store.setting('ai');ai.update(enabled=True,model='mock-integration',apiKey='not-a-real-api-key');db.execute('UPDATE settings SET data=? WHERE key=?',(json.dumps(ai),'ai'))
 class Response:
  def __init__(self,result):self.result=result
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self,*args):return json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(self.result)}]}]}).encode()
 def mock_result(result):return patch.object(creator,'urlopen',lambda *a,**kw:Response(result))
 for decision,rule,complete,expected in [('approve','允许介绍温和的呼吸觉察。',True,'published'),('reject','禁止虚假治疗承诺。',True,'rejected'),('approve','杜撰的审核依据',True,'manual_review'),('approve','允许介绍温和的呼吸觉察。',False,'manual_review')]:
  x=bob.req('POST','/api/creator/works',draft)['item']
  with mock_result(dict(decision=decision,reason='模型测试判断',rule=rule,complete=complete)):
   x=bob.req('POST','/api/creator/works/'+x['id']+'/submit',dict(version=x['version']))['item']
  assert x['status']==expected,(x,expected)
 x=bob.req('POST','/api/creator/works',draft)['item']
 with patch.object(creator,'urlopen',side_effect=TimeoutError()):x=bob.req('POST','/api/creator/works/'+x['id']+'/submit',dict(version=x['version']))['item']
 assert x['status']=='manual_review'
 checked('AI结构化接口模拟：自动通过、明确拒绝、伪造依据、不完整结果和超时转人工')
 x=bob.req('POST','/api/creator/works',draft)['item'];entered=threading.Event();release=threading.Event();worker_errors=[]
 def delayed(*args,**kwargs):
  entered.set();assert release.wait(10);return Response(dict(decision='approve',reason='延迟返回通过',rule='允许介绍温和的呼吸觉察。',complete=True))
 def submit_stale():
  try:bob.req('POST','/api/creator/works/'+x['id']+'/submit',dict(version=x['version']),status=409)
  except Exception as error:worker_errors.append(str(error))
 with patch.object(creator,'urlopen',delayed):
  worker=threading.Thread(target=submit_stale);worker.start();assert entered.wait(10)
  active=latest(bob,x['id']);assert active['status']=='ai_review'
  bob.req('POST','/api/creator/works/'+x['id']+'/withdraw',dict(version=active['version']))
  release.set();worker.join(10)
 assert not worker_errors and latest(bob,x['id'])['status']=='draft'
 x=bob.req('POST','/api/creator/works',draft)['item'];entered.clear();release.clear();reply=[]
 def submit_rule_change():
  try:reply.append(bob.req('POST','/api/creator/works/'+x['id']+'/submit',dict(version=x['version']))['item'])
  except Exception as error:worker_errors.append(str(error))
 with patch.object(creator,'urlopen',delayed):
  worker=threading.Thread(target=submit_rule_change);worker.start();assert entered.wait(10)
  admin.req('PUT','/api/admin/moderation-settings',dict(enabled=True,autoApprove=True,rules='允许介绍温和的呼吸觉察。禁止虚假治疗承诺。新增人工抽检规则。',knowledge='本平台关注日常练习与成长。'))
  release.set();worker.join(10)
 assert not worker_errors and reply[0]['status']=='manual_review'
 checked('在途AI结果不能覆盖撤回、审核规则版本改变后不得自动发布')
 admin.req('PATCH','/api/admin/creators/'+aid,dict(status='suspended',reason='专项核验暂停'))
 alice.req('GET','/api/creator/analytics',status=403);anon.req('GET','/api/creators/'+aid,status=404)
 assert not any(x['id']==c['id'] for x in anon.req('GET','/api/public')['content']['courses'])
 admin.req('PATCH','/api/admin/users/'+bid,dict(role='user'));bob.req('GET','/api/creator/works',status=403)
 assert not any(x.get('creatorId')==bid for x in anon.req('GET','/api/community/posts')['items'])
 checked('资格暂停与旧账号角色撤销同步下架并阻断访问')
 report={'at':datetime.now(timezone.utc).isoformat(),'pass':True,'checks':checks,'count':len(checks),'scope':'Isolated SQLite database; actual HTTP; mocked AI provider responses; no production requests or live model calls'}
 (ROOT/'06_验证与后续工作/创作者中心接口核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'pass':True,'checks':len(checks)}))
finally:
 httpd.shutdown();httpd.server_close()
 for suffix in ('','-wal','-shm'):
  file=Path(str(db_path)+suffix)
  if file.exists():file.unlink()
