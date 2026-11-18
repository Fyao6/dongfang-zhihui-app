"""Execute only planned gateway source in fresh SQLite; never apply helper or start service."""
from pathlib import Path
from contextlib import contextmanager,redirect_stdout
from types import ModuleType
import copy,hashlib,io,json,runpy,sys,threading,time
ROOT=Path(__file__).resolve().parents[1];BACK=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACK))
import account_write_guard as W,account_closure as M
from privacy import actual_binding
ns={}
prefix=(ROOT/'06_验证与后续工作/负责人优化建议-账号注销内存专项.py').read_text(encoding='utf-8').split('def closure():')[0]
ns['__file__']=str(ROOT/'06_验证与后续工作/负责人优化建议-账号注销内存专项.py');exec(compile(prefix,ns['__file__'],'exec'),ns)
with redirect_stdout(io.StringIO()):plan=runpy.run_path(str(ROOT/'06_验证与后续工作/负责人优化建议-账号注销接入准备.py'))
proposed=plan['changes'][BACK/'ai_gateway.py']
G=ModuleType('closure_planned_gateway');G.__file__=str(BACK/'ai_gateway.py');exec(compile(proposed,G.__file__,'exec'),G.__dict__)
results=[]
def check(name,fn):
 try:fn();results.append({'name':name,'pass':True})
 except Exception as e:results.append({'name':name,'pass':False,'error':type(e).__name__+': '+str(e)})
def scenario(save,close_during):
 f=ns['Fixture']();original=f.store.connect
 @contextmanager
 def connect():
  with original() as db:yield W.guard_connection(db)
 f.store.connect=connect
 p={'id':'primary','name':'Fixture','protocol':'responses','endpoint':'https://primary.example.test/v1/responses','model':'fixture','secretRef':'EW_AI_FIXTURE','processingRegions':['TEST-ONLY'],'privacyPolicyVersion':'fixture-policy','enabled':True,'streaming':True,'authMode':'bearer','apiVersion':'','timeoutSeconds':5,'maxOutputTokens':64,'prompt':''}
 privacy={'policyVersion':'fixture-policy','controllerName':'QA','contact':'QA','revision':1,'recipients':[{'id':'primary','name':'QA','endpoint':p['endpoint'],'models':['fixture'],'regions':['TEST-ONLY'],'purpose':'Synthetic fixture','policyUrl':'https://primary.example.test/privacy'}],'retention':{'recordsDays':None,'conversationsDays':None,'backupDays':None,'financeDays':None},'purposeDetails':{'trainingImprovement':'','marketing':''}}
 legacy={'providerId':'primary','endpoint':p['endpoint'],'model':'fixture','processingRegions':['TEST-ONLY'],'privacyPolicyVersion':'fixture-policy'}
 flags={k:False for k in ['chart','wellbeing','saveConversations','longTermMemory','trainingImprovement','marketing']};flags['saveConversations']=save
 with f.store.connect() as db:
  for k,v in [('privacy',privacy),('ai',legacy)]:db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(k,json.dumps(v)))
  db.execute("UPDATE privacy_preferences SET data=?,policy_version='fixture-policy',provider_binding=? WHERE user_id='buyer'",(json.dumps(flags),actual_binding(privacy,legacy)['digest']))
  db.execute("DELETE FROM privacy_conversations WHERE user_id='buyer'")
 close_errors=[]
 class Response:
  headers={'request-id':'LOCAL_FIXTURE'}
  def __iter__(self):
   events=['event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"synthetic"}\n\n','event: response.completed\ndata: {"type":"response.completed","response":{"usage":{"input_tokens":7,"output_tokens":3}}}\n\n']
   for index,event in enumerate(events):
    if close_during and index==1:
     def close():
      try:f.close(ns['Handler'](f))
      except Exception as e:close_errors.append(str(e))
     thread=threading.Thread(target=close);thread.start();thread.join(10);assert not thread.is_alive()
    for line in event.splitlines(keepends=True):yield line.encode()
  def close(self):pass
 def transport(*args):return Response()
 h=f.h;admin=ns['Handler'](f,'admin')
 gate=G.AIGateway(f.store,h,ns['Error'],lambda *a:None,test_transport=transport,test_secret_resolver=lambda _: 'SYNTHETIC')
 ag=G.AIGateway(f.store,admin,ns['Error'],lambda *a:None,test_transport=transport,test_secret_resolver=lambda _: 'SYNTHETIC')
 cfg=copy.deepcopy(G.DEFAULT);cfg.update({'enabled':True,'allowExternalCalls':True,'providers':[p],'routes':{s:{'primary':'primary','fallback':[]} for s in G.SCENES},'charging':{'confirmed':True,'ruleVersion':'fixture-rule','successCredits':3,'failureCredits':1,'partialCredits':2,'cancelCredits':2}})
 admin.data=cfg;admin.path='/api/admin/ai-gateway/config';ag.route('PATCH',admin.path)
 admin.data={'requestId':'fixture-grant','accountId':'buyer','credits':100,'environment':'local-test'};ag.route('POST','/api/admin/ai-gateway/grants')
 auth=gate.authorization(gate.provider('primary'),require_receipt=False)
 h.data={'acknowledged':True,'policyVersion':auth['policyVersion'],'providerBinding':auth['providerBinding'],'categories':['general']};gate.route('POST','/api/ai-gateway/providers/primary/consent')
 auth=gate.authorization(gate.provider('primary'));tag={k:auth[k] for k in ['accountId','providerId','providerBinding','policyVersion','consentEpoch']};tag.update(source='user',category='general')
 body={'requestId':'fixture-runtime','scene':'chat','environment':'local-test','messages':[{'role':'user','content':'synthetic','privacy':tag}],'context':None}
 actor=W.begin_actor('buyer',M.digest(h.session_token));events=[]
 try:
  job=gate.create_job(body);gate.run(job['id'],body,lambda e,d:events.append((e,d)))
 finally:W.end_actor(actor)
 assert not close_errors,close_errors
 with f.store.connect() as db:
  row=db.execute('SELECT * FROM ai_gateway_jobs WHERE id=?',(job['id'],)).fetchone()
  wallet=db.execute("SELECT * FROM ai_gateway_wallets WHERE owner='buyer'").fetchone()
  stored=db.execute("SELECT count(*) FROM privacy_conversations WHERE user_id='buyer'").fetchone()[0]
  assert row['status']==('cancelled' if close_during else 'succeeded'),dict(row)
  assert wallet['balance']==(98 if close_during else 97) and wallet['reserved']==0
  assert stored==(1 if save and not close_during else 0),stored
 assert any(e=='gateway.done' for e,d in events)
check('planned Python gateway save=true uses conditional guarded INSERT and completes quota settlement',lambda:scenario(True,False))
check('planned Python gateway save=false still settles without storing body',lambda:scenario(False,False))
check('actual authoritative closure during provider events prevents body revival and still settles charged cancellation',lambda:scenario(True,True))
report={'scope':'planned gateway source executed in fresh SQLite, real closure/guard/authority; no shared edits, service, real model or original DB','passed':sum(x['pass'] for x in results),'failed':sum(not x['pass'] for x in results),'results':results,'plannedGatewaySha256':hashlib.sha256(proposed.encode()).hexdigest(),'sourceSha256':{n:hashlib.sha256((BACK/n).read_bytes()).hexdigest() for n in ['account_closure.py','account_write_guard.py','privacy_retention.py']}}
out=Path(__file__).with_suffix('.json');old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {};out.write_text(json.dumps({'latest':report,'runs':old.get('runs',[])+[report]},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['passed','failed']}));sys.exit(bool(report['failed']))
