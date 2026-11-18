"""Owned actual HTTP component; never a formal-suite or professional claim."""
import argparse,copy,hashlib,http.cookiejar,json,pathlib,secrets,sys,threading,time,urllib.error,urllib.request,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
from server import Store,make_handler,ThreadingHTTPServer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expect-ready',action='store_true');args=parser.parse_args()
    run=uuid.uuid4().hex;folder=ROOT/'06_验证与后续工作';dbfile=folder/('bazi-http-component-'+run+'.sqlite3');store=Store(dbfile)
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(store,ROOT/'03_当前APP'));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
    report={'kind':'owned-http-component-not-formal','runId':run,'at':time.time(),'base':base,'database':str(dbfile.relative_to(ROOT)),'results':[],'professionalValidation':False,'teacherConfirmed':False,'priorFailure':{'code':'schema_path_used_parent_with_name','fixed':True,'originalFailedOwnedDatabase':'bazi-component-schema-owned.sqlite3'}}
    def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    admin=client();anonymous=client()
    def request(c,path,method='GET',data=None,raw=None,headers=None,expected=200):
        body=raw if raw is not None else json.dumps(data,ensure_ascii=False,separators=(',',':')).encode() if data is not None else None
        req=urllib.request.Request(base+path,data=body,method=method,headers={'Content-Type':'application/json',**(headers or {})})
        try:r=c.open(req,timeout=25);status=r.status;value=json.loads(r.read())
        except urllib.error.HTTPError as error:status=error.code;value=json.loads(error.read())
        if status!=expected:raise AssertionError({'path':path,'expected':expected,'actual':status,'error':value.get('error')})
        return value
    def check(name,fn):
        try:value=fn();report['results'].append({'name':name,'pass':True,'evidence':value})
        except Exception as error:report['results'].append({'name':name,'pass':False,'error':str(error)[:500]});raise
    path='/api/admin/bazi-samples'
    try:
        request(admin,'/api/auth/setup','POST',{'username':'component_'+run[:8],'password':secrets.token_urlsafe(18),'name':'Owned synthetic admin'})
        fixture=json.loads((folder/'负责人优化建议-八字样本夹具.json').read_bytes())['baseDataset'];data=copy.deepcopy(fixture);data['setId']='component-'+run;data['cases']=data['cases'][:1];case=data['cases'][0];case['expected']={'/originalInput/date':{'state':'value','value':case['input']['date']}}
        raw=json.dumps(data,ensure_ascii=False,indent=2).encode();key='import-'+run
        check('anonymous denied',lambda:request(anonymous,path,expected=401))
        imported=request(admin,path+'/import','POST',raw=raw,headers={'X-EW-Request-ID':key});vid=imported['item']['id']
        check('actual original UTF8 bytes SHA',lambda: {'equal':imported['item']['sourceBytesSha256']==hashlib.sha256(raw).hexdigest()} if imported['item']['sourceBytesSha256']==hashlib.sha256(raw).hexdigest() else (_ for _ in ()).throw(AssertionError('raw SHA')))
        replay=request(admin,path+'/import','POST',data=data,headers={'X-EW-Request-ID':'canonical-'+run})
        check('canonical same version preserves first bytes',lambda: {'sameId':replay['item']['id']==vid,'sameSHA':replay['item']['sourceBytesSha256']==imported['item']['sourceBytesSha256']} if replay['item']['id']==vid and replay['item']['sourceBytesSha256']==imported['item']['sourceBytesSha256'] else (_ for _ in ()).throw(AssertionError('canonical replay')))
        check('duplicate decoded key rejected',lambda:request(admin,path+'/import','POST',raw=b'{"schema":1,"schema":1}',headers={'X-EW-Request-ID':'duplicate-'+run},expected=400))
        check('BOM rejected',lambda:request(admin,path+'/import','POST',raw=b'\xef\xbb\xbf'+raw,headers={'X-EW-Request-ID':'bom-'+run},expected=400))
        header=request(admin,path+'/'+vid);check('full caseIds header',lambda:{'count':len(header['header']['caseIds'])})
        create={'requestId':'run-'+run,'setVersionId':vid,'caseIds':[case['caseId']]}
        if not args.expect_ready:
            check('old or incomplete APP binding is never ready',lambda:request(admin,path+'/runs','POST',data=create,expected=503))
        else:
            created=request(admin,path+'/runs','POST',data=create);rid=created['run']['id'];body={'requestId':'process-'+run,'version':created['run']['version'],'limit':1}
            processed=request(admin,path+'/runs/'+rid+'/process','POST',data=body)
            check('actual managed Node compute committed',lambda:{'processed':processed['run']['processed'],'state':processed['item']['state']} if processed['run']['processed']==1 and processed['item']['state']=='succeeded' else (_ for _ in ()).throw(AssertionError('process failed')))
            same=request(admin,path+'/runs/'+rid+'/process','POST',data=body);check('process intent replay does not advance',lambda:{'sameResult':same['item']['id']==processed['item']['id'],'processed':same['run']['processed']} if same['item']['id']==processed['item']['id'] and same['run']['processed']==1 else (_ for _ in ()).throw(AssertionError('process replay')))
            cp=path+'/runs/'+rid+'/cases/'+case['caseId'];full=request(admin,cp+'/export?includeName=1');safe=request(admin,cp+'/export');check('default name redaction, explicit full export',lambda:{'defaultNameAbsent':'name' not in safe['sampleCase']['input'],'fullNameRetained':full['sampleCase']['input']['name']==case['input']['name']} if 'name' not in safe['sampleCase']['input'] and full['sampleCase']['input']['name']==case['input']['name'] else (_ for _ in ()).throw(AssertionError('name policy')))
            index=request(admin,cp+'/raw');periods=[request(admin,cp+'/raw/periods/'+str(i))['data'] for i in range(len(index['index']['periods']))];actual={**index['header'],'periods':periods};canonical=json.dumps(actual,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();check('all 10 raw periods restore frozen SHA',lambda:{'periods':len(periods),'hashMatches':hashlib.sha256(canonical).hexdigest()==index['index']['sha256']} if len(periods)==10 and hashlib.sha256(canonical).hexdigest()==index['index']['sha256'] else (_ for _ in ()).throw(AssertionError('raw mismatch')))
            fields=request(admin,cp+'/fields');second=request(admin,cp+'/fields?before='+urllib.parse.quote(fields['next'],safe=''));check('lazy frozen fields 50 and same-scope cursor',lambda:{'first':len(fields['items']),'second':len(second['items'])} if len(fields['items'])==len(second['items'])==50 else (_ for _ in ()).throw(AssertionError('field page')))
            detail=request(admin,cp);check('detail preserves original input for explicit APP comparison',lambda:{'sameName':detail['sampleCase']['input']['name']==case['input']['name']})
            field_path='/originalInput/date';paths=[r['path'] for r in full['report']['fieldIndex']];cursor=paths[paths.index(field_path)-1];finding=next(f for f in request(admin,cp+'/fields?before='+urllib.parse.quote(cursor,safe=''))['items'] if f['path']==field_path)
            review_body={'requestId':'review-'+run,'category':'input','evidence':{'paths':[field_path],'fingerprints':full['report']['fingerprints'],'reference':'owned synthetic component'},'note':'A proposed comparison classification, never teacher approval.','retestRunId':None}
            review=request(admin,path+'/findings/'+finding['id']+'/reviews','POST',data=review_body);review_replay=request(admin,path+'/findings/'+finding['id']+'/reviews','POST',data=review_body);reviews=request(admin,cp)['reviews']
            assert review['item']['id']==review_replay['item']['id'] and len(reviews)==1 and reviews[0]['classificationState']=='proposed';check('append-only proposed review is idempotent and rereadable',lambda:{'reviewCount':1,'classificationState':'proposed'})
            report['rawProof']={'sha256':index['index']['sha256'],'byteLength':index['index']['byteLength'],'periodCount':len(periods),'domStatus':'not_run'}
            retry=request(admin,path+'/runs','POST',data={'requestId':'fault-run-'+run,'setVersionId':vid,'caseIds':[case['caseId']]});retry_id=retry['run']['id'];retry_body={'requestId':'fault-process-'+run,'version':retry['run']['version'],'limit':1}
            with store.connect() as db:db.execute("CREATE TRIGGER bazi_component_fault BEFORE INSERT ON bazi_sample_raw_chunks BEGIN SELECT RAISE(ABORT,'owned_component_storage_failure'); END")
            request(admin,path+'/runs/'+retry_id+'/process','POST',data=retry_body,expected=409)
            with store.connect() as db:
                current=db.execute('SELECT processed FROM bazi_sample_runs WHERE id=?',(retry_id,)).fetchone()[0];n=db.execute('SELECT count(*) FROM bazi_sample_results WHERE run_id=?',(retry_id,)).fetchone()[0]
                assert current==n==0;check('real storage exception leaves no partial result/field/chunks',lambda:{'processed':current,'results':n})
                db.execute('DROP TRIGGER bazi_component_fault');db.execute('UPDATE bazi_sample_workitems SET lease_until=0 WHERE run_id=?',(retry_id,))
            recovered=request(admin,path+'/runs/'+retry_id+'/process','POST',data=retry_body)
            with store.connect() as db:
                attempts=db.execute('SELECT attempts FROM bazi_sample_workitems WHERE run_id=?',(retry_id,)).fetchone()[0]
                assert recovered['run']['processed']==1 and recovered['item']['state']=='succeeded' and attempts==2;check('same intent resumes after genuinely expired lease',lambda:{'processed':1,'attempts':attempts})
        cleared=request(admin,'/api/privacy/requests','POST',{'kind':'delete-records','requestId':'erase-'+run});check('real privacy clear proof same TX',lambda:cleared['item']['details']['local']['deletedCounts']['baziSamples'])
        check('erased version inaccessible',lambda:request(admin,path+'/'+vid,expected=410))
        with store.connect() as db:
            counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('bazi_sample_cases','bazi_sample_results','bazi_sample_raw_chunks','bazi_sample_field_results','bazi_sample_reviews','bazi_sample_erase_guards')}
            assert all(v==0 for v in counts.values());check('actual private rows deleted, transient guards zero',lambda:counts)
            check('DB integrity',lambda:{'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]})
    except Exception as error:
        if not report['results'] or report['results'][-1]['pass']:report['results'].append({'name':'unexpected component failure','pass':False,'error':str(error)[:500]})
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report['passed']=sum(r['pass'] for r in report['results']);report['failed']=sum(not r['pass'] for r in report['results']);report['ownedServerStopped']=not thread.is_alive();report['actualFullReadyRun']=args.expect_ready
        report['sourceHashes']={str((ROOT/p).relative_to(ROOT)):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['04_研发源码/app/r4/backend/bazi_samples.py','04_研发源码/app/r4/backend/bazi_samples_schema.sql']}
        destination=folder/('负责人优化建议-八字样本后端组件-python-'+run+'.json');destination.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'report':destination.name,'passed':report['passed'],'failed':report['failed'],'ownedServerStopped':report['ownedServerStopped']},ensure_ascii=True));return 1 if report['failed'] else 0
if __name__=='__main__':sys.exit(main())
