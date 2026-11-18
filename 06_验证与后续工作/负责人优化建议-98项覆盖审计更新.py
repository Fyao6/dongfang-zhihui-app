"""Prepared only. Read current tasks/evidence; do not modify tasks or old audit by default.

Final --write requires final bridge and after-sales records, every explicit additional final record, and a frozen flag.
Without --replace-existing writes a review draft only. No business source/DB/network use.
"""
import argparse,hashlib,json,re
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作'
TASKS=OUT/'负责人优化建议-任务拆解.json';AUDIT=OUT/'负责人优化建议-98项最终覆盖审计.json';TEXT=AUDIT.with_suffix('.txt')
ARCHIVE_RECORD='06_验证与后续工作/负责人优化建议-只读对账-实施记录.json'
ARCHIVE_RECORD_SHA='d7d98c1791ec79a0c1bfede4959ffdf3128fbbf5377a21823f3ea77805d7731f'
ARCHIVE_CORRECTION='06_验证与后续工作/负责人优化建议-只读对账-归档哈希更正.json'
ARCHIVE_REPORTS={
 'Python全量':'06_验证与后续工作/负责人优化建议-只读对账-本机全量验收.json',
 'Cloud全量':'06_验证与后续工作/负责人优化建议-只读对账-本地Cloud全量验收.json',
 'Python专项':'06_验证与后续工作/负责人优化建议-只读对账-Python专项验收.json',
 'Cloud专项':'06_验证与后续工作/负责人优化建议-只读对账-Cloud专项验收.json',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def permitted(p):
    p=p.resolve();assert p.is_relative_to(OUT.resolve()),'Evidence must remain under 06';assert p.suffix in ('.json','.txt'),('Not a report',p.name);return p
def archive_correction(record_path,label,snapshot,declared_sha):
    """Exact additive correction only; never rewrite an old expected hash or report."""
    if record_path is None or record_path.resolve()!=(ROOT/ARCHIVE_RECORD).resolve():return None
    assert sha(record_path)==ARCHIVE_RECORD_SHA,'Original reconciliation record drifted'
    correction_path=permitted(ROOT/ARCHIVE_CORRECTION);c=read(correction_path)
    assert c.get('pass') is True and c.get('kind')=='additive-archive-hash-correction'
    assert c.get('originalRecord')==ARCHIVE_RECORD and c.get('originalRecordSha256')==ARCHIVE_RECORD_SHA
    assert c.get('originalCommit')=='0792e22' and c.get('allOriginalEvidenceBytesPreserved') is True
    entries=c.get('corrections');assert isinstance(entries,list) and len(entries)==4
    assert {x.get('label'):x.get('path') for x in entries}==ARCHIVE_REPORTS,'Correction scope differs from four original reports'
    if label not in ARCHIVE_REPORTS or snapshot.resolve()!=(ROOT/ARCHIVE_REPORTS[label]).resolve():return None
    matches=[x for x in entries if x.get('label')==label];assert len(matches)==1
    item=matches[0];actual=sha(snapshot);lf=hashlib.sha256(snapshot.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert item.get('matchesOriginalCommitBytes') is True
    assert item.get('originalRecordedSha256')==declared_sha==item.get('lfNormalizedSha256')==lf,'LF-normalized bytes do not match original declaration'
    assert item.get('actualFileSha256')==actual and actual!=declared_sha,'Unexpected archive byte hash'
    return {'validated':True,'path':ARCHIVE_CORRECTION,'sha256':sha(correction_path),'originalRecord':ARCHIVE_RECORD,'originalRecordSha256':ARCHIVE_RECORD_SHA,'originalCommit':'0792e22','originalDeclarationMismatch':True,'originalRecordedSha256':declared_sha,'actualFileSha256':actual,'lfNormalizedSha256':lf,'status':'original-declaration-mismatched-additive-correction-verified','allOriginalEvidenceBytesPreserved':True}
def observed_gate(report):
    """Inspect every entry; absent pass/counts remain absent, never invented."""
    result={k:report[k] for k in ('pass','passed','failed','identityUnchanged') if k in report}
    lists={}
    for key in ('checks','results'):
        if key not in report:continue
        values=report[key]
        if not isinstance(values,list):
            lists[key]={'completeListObserved':False,'reason':'not-a-list'};continue
        items=[];passed=failed=unrecognized=0
        for item in values:
            flags={k:item[k] for k in ('pass','passed') if k in item} if isinstance(item,dict) else {}
            known=bool(flags) and all(type(v) is bool for v in flags.values()) and len(set(flags.values()))==1
            flag=next(iter(flags.values())) if known else None
            passed+=flag is True;failed+=flag is False;unrecognized+=not known
            items.append({'name':item.get('name') if isinstance(item,dict) else None,'observedFlags':flags,'recognized':known})
        lists[key]={'completeListObserved':True,'length':len(values),'passCount':passed,'failCount':failed,'unrecognizedCount':unrecognized,'allPassed':bool(values) and passed==len(values),'items':items}
    result['lists']=lists
    if all(key in report for key in ('ran','failures','errors','output')):
        output=report['output'] if isinstance(report['output'],str) else ''
        cases=[{'name':m[0],'class':m[1],'status':m[2]} for m in re.findall(r'^(test_\S+) \(([^)]+)\) \.\.\. ([^\r\n]+)$',output,re.M)]
        summary=re.findall(r'^Ran (\d+) tests? in [^\r\n]+$',output,re.M)
        result['nativeUnittest']={'ran':report['ran'],'failures':report['failures'],'errors':report['errors'],'cases':cases,'summaryCounts':[int(x) for x in summary],'originalOutputEndsOK':bool(re.search(r'^OK\s*\Z',output,re.M))}
    if 'completed' in report and all(isinstance(report.get(target),dict) and isinstance(report[target].get('captures'),list) for target in ('python','cloud')):
        captures=[]
        for target in ('python','cloud'):
            for capture in report[target]['captures']:
                if not isinstance(capture,dict):
                    captures.append({'target':target,'validEntry':False});continue
                name=str(capture.get('path','')).replace('\\','/')
                file=(ROOT/name).resolve()
                allowed=file.is_relative_to(OUT.resolve()) and file.suffix.lower()=='.png'
                actual=sha(file) if allowed and file.is_file() else None
                captures.append({'target':target,'path':name,'declaredSha256':capture.get('sha256'),'actualSha256':actual,'bytesVerified':actual is not None and actual==capture.get('sha256'),'viewed':capture.get('viewed'),'pass':capture.get('pass')})
        result['nativeVisualReview']={'completed':report.get('completed'),'targets':{target:{'runId':report[target].get('runId'),'reportSha256':report[target].get('reportSha256'),'images':len(report[target]['captures'])} for target in ('python','cloud')},'captures':captures}
    return result
def reference_validation(ref):
    reasons=[];gate=ref.get('observedGate',{});declared=ref.get('declaredPassed');counted=type(declared) is int
    if not ref.get('exists'):reasons.append('missing-snapshot')
    if not ref.get('frozenEvidenceMatches',ref.get('frozenShaMatches')):reasons.append('missing-or-mismatched-frozen-sha256')
    if not gate:reasons.append('missing-json-gate')
    lists=list(gate.get('lists',{}).values())
    complete=bool(lists) and all(x.get('completeListObserved') and x.get('allPassed') and x.get('unrecognizedCount')==0 for x in lists)
    if lists and not complete:reasons.append('incomplete-or-failed-checks/results-list')
    application=ref.get('applicationAudit')
    if isinstance(application,dict):
        reasons.extend(application['reasons'])
        return {'validated':not reasons,'mode':'application-provenance-linked-to-frozen-actual-identities','reasons':reasons}
    visual=gate.get('nativeVisualReview')
    if isinstance(visual,dict):
        images=ref.get('declaredImages');captures=visual['captures']
        if visual['completed'] is not True:reasons.append('native-visual-review-not-completed')
        if type(images) is not int or images<1 or len(captures)!=images:reasons.append('native-visual-image-count-mismatch')
        if len({x.get('path') for x in captures})!=len(captures):reasons.append('native-visual-duplicate-captures')
        if any(x.get('viewed') is not True or x.get('pass') is not True or x.get('bytesVerified') is not True for x in captures):reasons.append('native-visual-not-reviewed-passing-exact-bytes')
        if any(x['images']<1 or not re.fullmatch(r'[a-z0-9]+_[a-f0-9]{6}',str(x['runId'])) or not re.fullmatch(r'[a-f0-9]{64}',str(x['reportSha256'])) for x in visual['targets'].values()):reasons.append('native-visual-original-run-identity-missing')
        return {'validated':not reasons,'mode':'completed-original-visual-review-with-exact-captures','reasons':reasons}
    native=gate.get('nativeUnittest')
    if counted and isinstance(native,dict):
        cases=native['cases']
        if gate.get('pass') is not True:reasons.append('native-unittest-requires-explicit-pass')
        if any(type(native[k]) is not int for k in ('ran','failures','errors')):reasons.append('native-unittest-counter-types')
        if native['ran']!=declared or declared<1 or native['failures']!=0 or native['errors']!=0:reasons.append('native-unittest-counters-do-not-match')
        if len(cases)!=declared or len({(x['name'],x['class']) for x in cases})!=declared or any(x['status']!='ok' for x in cases):reasons.append('native-unittest-original-cases-not-all-ok')
        if native['summaryCounts']!=[declared] or not native['originalOutputEndsOK']:reasons.append('native-unittest-original-summary-does-not-match')
        return {'validated':not reasons,'mode':'native-unittest-counts-with-original-output','reasons':reasons}
    if counted:
        if declared<0:reasons.append('invalid-declared-count')
        if type(gate.get('passed')) is not int or gate['passed']!=declared:reasons.append('passed-count-does-not-match-declared')
        if type(gate.get('failed')) is not int or gate['failed']!=0:reasons.append('missing-or-nonzero-failed-count')
        if lists and any(x.get('length')!=declared for x in lists):reasons.append('complete-list-length-does-not-match-count')
        if 'pass' in gate:
            if gate['pass'] is not True:reasons.append('explicit-pass-not-true')
            mode='counted-explicit-pass'
        else:
            mode='counted-complete-original-list'
            # Main regression/actual gates retain explicit pass=true as well as counts.
            if declared in (60,29,31,16):reasons.append('primary-gate-requires-explicit-pass')
            if not complete:reasons.append('missing-pass-requires-complete-original-checks/results')
    else:
        mode='non-counted-explicit-pass'
        if declared is not None:reasons.append('invalid-declared-passed-type')
        if gate.get('pass') is not True:reasons.append('non-counted-report-requires-explicit-pass')
        if 'failed' in gate and (type(gate['failed']) is not int or gate['failed']!=0):reasons.append('invalid-or-nonzero-failed-count')
        if 'passed' in gate and (type(gate['passed']) is not int or gate['passed']<0):reasons.append('invalid-observed-passed-count')
        # A visual receipt can have no counters/lists. Preserve that schema, no fake count.
    return {'validated':not reasons,'mode':mode,'reasons':reasons}
def application_audit(report,record):
    reasons=[];changes=report.get('sourceChanges',[]);anchors=report.get('anchors',[])
    paths=[str(x.get('path','')).replace('\\','/') for x in changes if isinstance(x,dict)]
    if report.get('mode')!='apply' or report.get('pendingDependencyAnchors')!=[]:reasons.append('application-was-not-applied-with-complete-dependencies')
    if not changes or len(paths)!=len(changes) or len(set(paths))!=len(paths):reasons.append('application-source-list-invalid')
    for item,path in zip(changes,paths):
        if not path.startswith('04_研发源码/app/') or not (ROOT/path).resolve().is_relative_to(ROOT.resolve()) or any(not re.fullmatch(r'[a-f0-9]{64}',str(item.get(key))) for key in ('beforeSha256','afterSha256')):reasons.append('application-source-hash-invalid')
    if not anchors or any(not isinstance(x,dict) or str(x.get('file','')).replace('\\','/') not in paths or not x.get('label') for x in anchors):reasons.append('application-anchors-invalid')
    identities={}
    for value in record.get('verification',{}).values():
        if not isinstance(value,dict) or not value.get('path'):continue
        file=permitted(ROOT/value['path'])
        if not file.is_file() or sha(file)!=value.get('sha256'):continue
        snapshot=read(file);snapshot=snapshot.get('latest',snapshot)
        target=snapshot.get('target');mapping=snapshot.get('sourceBuildTestHashes')
        if target in ('python','cloud') and snapshot.get('pass') is True and isinstance(mapping,dict):
            identities[target]={'snapshot':file.relative_to(ROOT).as_posix(),'sha256':sha(file),'hashes':{str(k).replace('\\','/'):v for k,v in mapping.items()}}
    if set(identities)!={'python','cloud'}:reasons.append('application-missing-two-frozen-actual-identities')
    for target,value in identities.items():
        if any(value['hashes'].get(path)!=item.get('afterSha256') for path,item in zip(paths,changes)):reasons.append('application-after-bytes-not-in-frozen-'+target)
    return {'mode':report.get('mode'),'sourceFiles':len(changes),'anchors':len(anchors),'pendingDependencyAnchors':report.get('pendingDependencyAnchors'),'actualIdentityEvidence':{k:{'path':v['snapshot'],'sha256':v['sha256']} for k,v in identities.items()},'reasons':reasons,'isTestPassAssertion':False}

def references(record,record_path=None):
    refs=[]
    for name,value in record.get('verification',{}).items():
        if not isinstance(value,dict):continue
        raw=value.get('path')
        if not raw:refs.append({'name':name,'state':'missing-path'});continue
        p=permitted(ROOT/raw);entry={'name':name,'path':str(p.relative_to(ROOT)).replace('\\','/'),'exists':p.is_file(),'declaredPassed':value.get('passed'),'declaredImages':value.get('images'),'declaredSha256':value.get('sha256'),'at':value.get('at')}
        if p.is_file():
            entry['sha256']=sha(p);entry['frozenShaMatches']=isinstance(value.get('sha256'),str) and value['sha256']==entry['sha256']
            entry['frozenEvidenceMatches']=entry['frozenShaMatches'];entry['hashMatchMethod']='direct-bytes' if entry['frozenShaMatches'] else 'mismatch'
            if not entry['frozenShaMatches']:
                correction=archive_correction(record_path,name,p,value.get('sha256'))
                if correction:
                    entry['archiveCorrection']=correction;entry['frozenEvidenceMatches']=True;entry['hashMatchMethod']='explicit-additive-LF-CRLF-correction'
            if p.suffix=='.json':
                r=read(p);r=r.get('latest',r);entry['observedGate']=observed_gate(r)
                if value.get('passed') is None and all(k in r for k in ('mode','sourceChanges','anchors','pendingDependencyAnchors','backupMapping')):
                    entry['applicationAudit']=application_audit(r,record)
        entry['validation']=reference_validation(entry)
        refs.append(entry)
    return refs
def evidence(p):
    p=permitted(p);r=read(p)
    return {'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p),'module':r.get('module'),'pass':r.get('pass'),'at':r.get('at_beijing',r.get('at')),'scope':r.get('scope'),'limitations':r.get('limitations',[]),'verification':references(r,p),'historicalStageEvidence':True}
def final_record(p,label):
    assert p is not None,label+' final record is required';p=permitted(p if p.is_absolute() else ROOT/p);r=read(p)
    assert r.get('pass') is True,(label,'not frozen pass');refs=references(r,p);assert refs,(label,'no verifiable reports')
    for ref in refs:
        assert ref.get('validation',{}).get('validated'),(label,ref['name'],ref.get('validation'))
    return p
def compact(v):return str(v).replace('\n',' ').replace('|','／')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bridge-record',type=Path);ap.add_argument('--after-sales-record',type=Path);ap.add_argument('--check-record',type=Path,help='Validate one frozen record only; no audit/task writes');ap.add_argument('--final-integrations-frozen',action='store_true');ap.add_argument('--write',action='store_true');ap.add_argument('--replace-existing',action='store_true');ap.add_argument('--additional-final-record',type=Path,action='append',default=[],help='Verify an additional frozen local module record, including every reference, before final audit');args=ap.parse_args()
    if args.check_record:
        assert not args.write and not args.replace_existing,'--check-record never writes'
        p=final_record(args.check_record,'single-record');refs=references(read(p),p)
        print(json.dumps({'mode':'single-record-read-only','record':str(p.relative_to(ROOT)),'validated':True,'references':[{'name':r['name'],'declaredPassed':r.get('declaredPassed'),**{'observed'+k.title():r['observedGate'][k] for k in ('passed','failed') if k in r['observedGate']},'explicitPassPresent':'pass' in r['observedGate'],'mode':r['validation']['mode'],'listLengths':{k:v.get('length') for k,v in r['observedGate']['lists'].items()},'frozenShaMatches':r['frozenShaMatches']} for r in refs],'auditWritten':False,'taskJSONModified':False},ensure_ascii=False,indent=2));return
    assert not args.replace_existing or args.write,'--replace-existing requires --write'
    before=sha(TASKS);tasks=read(TASKS);old=read(AUDIT);template=read(OUT/'负责人优化建议-98项覆盖审计更新模板.json')
    ids=[t['id'] for t in tasks];assert len(ids)==98 and len(set(ids))==98
    previous={t['id']:t for t in old['rows']};assert set(previous)==set(ids),'Unexpected task set change; review source mapping'
    bridge=sales=None
    additional=[final_record(p,'additional-module') for p in args.additional_final_record]
    if args.write:
        assert args.final_integrations_frozen,'Wait for root final bridge + after-sales freeze notification'
        bridge=final_record(args.bridge_record,'bridge');sales=final_record(args.after_sales_record,'after-sales')
    catalog={}
    for p in sorted(OUT.glob('负责人优化建议-*实施记录.json')):
        catalog[p.name]=evidence(p)
    for p in [bridge,sales,*additional]:
        if p:catalog[p.name]=evidence(p)
    rows=[]
    for task in tasks:
        ident=task['id'];ov=template['rowOverrides'].get(ident,{});names=list(ov.get('records',[]));declared=task.get('verification_record')
        if declared:names.append(Path(declared).name)
        if bridge and ov.get('takeBridgeFinalRecord'):names.append(bridge.name)
        if sales and ov.get('takeAfterSalesFinalRecord'):names.append(sales.name)
        selected=[catalog[n] for n in dict.fromkeys(names) if n in catalog]
        if ov.get('requiredStatus'):assert task['status']==ov['requiredStatus'],(ident,'must not claim overall completion')
        extra=[]
        for name in ov.get('additionalEvidence',[]):
            p=permitted(OUT/name);extra.append({'path':str(p.relative_to(ROOT)).replace('\\','/'),'exists':p.is_file(),'sha256':sha(p) if p.is_file() else None})
        rows.append({'id':ident,'title':task['title'],'module':task['module'],'source_ids':task['source_ids'],'requirement':task['detail'],'acceptance':task['acceptance'],'task_table_status_at_audit':task['status'],'declaredCurrentScope':task.get('implementation_note','未提供实现说明'),'stage':task.get('implementation_note','当前实现范围未说明'),'resolvedSoftware':ov.get('resolvedSoftware',[]),'softwareNotImplemented':ov.get('softwareNotImplemented',[]),'softwareGapEvidence':ov.get('softwareGapEvidence',[]),'currentSoftwareBoundary':ov.get('currentSoftwareBoundary',{}),'externalInputs':ov.get('externalInputs',[]),'productionOrAcceptanceGates':ov.get('productionGates',[]),'unclassifiedDependencies':task.get('dependencies',''),'softwareAssessmentBasis':'explicit override + current note + scoped record; empty gaps do not prove completion','evidence':selected,'additionalEvidence':extra,'previousAuditReference':{'stage':previous[ident].get('stage'),'local_next':previous[ident].get('local_next'),'external_blocker':previous[ident].get('external_blocker'),'historicalOnly':True}})
    critical=[{'taskIds':[r['id']],'softwareNotImplemented':r['softwareNotImplemented'],'externalInputs':r['externalInputs'],'productionGates':r['productionOrAcceptanceGates']} for r in rows if r['id'] in ('PR03','PR04','PR05','PR06','SV04','PAY16','PAY18','SH03','SH04','SH05','PAY19')]
    official=OUT/'负责人优化建议-26项官方资料复核.json'
    result={'audit_kind':'98项当前范围与剩余工作的证据索引，不是98项完成证明','at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'finalIntegrationsFrozen':bool(bridge and sales),'additionalFinalRecordChecks':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'allReferencesValidated':True} for p in additional],'scope':{'taskJSONModified':False,'businessSourceModified':False,'entryOrBuildModified':False,'originalDatabaseRead':False,'networkRequestMade':False,'environmentValuesRead':False},'reviewed':{'taskCount':98,'allCurrentTaskFieldsRead':True,'originalDocumentInstructionsTreatedAsSourceMaterial':True},'currentTaskStatusCounts':dict(Counter(t['status'] for t in tasks)),'statusCountIsDeclarationNotProductionAcceptance':True,'critical':critical,'rows':rows,'evidenceCatalog':catalog,'officialSources':{'path':str(official.relative_to(ROOT)),'sha256':sha(official) if official.exists() else None,'browseRepeated':False},'source_artifacts':{'taskJSON':{'path':str(TASKS.relative_to(ROOT)),'sha256':before},'previousAudit':{'path':str(AUDIT.relative_to(ROOT)),'sha256':sha(AUDIT)},'template':{'path':str((OUT/'负责人优化建议-98项覆盖审计更新模板.json').relative_to(ROOT)),'sha256':sha(OUT/'负责人优化建议-98项覆盖审计更新模板.json')}},'coverage_check':{'uniqueTaskIds':98,'sameTaskSetAsPreviousAudit':True,'taskSourceIdsPreserved':True},'limitations':['实施说明是当前任务记录声明，实证范围以各冻结报告scope和限制为准；旧阶段证据不等于当前生产环境验收。','软件缺口、外部输入与生产/目标设备门禁分列；未列额外缺口不等于实现完毕。','此前审计stage/next仅作历史参考，已修guarded保存/新集成模块不得按旧说明重复派工。','此脚本不推导任务状态、不更新任务JSON，不以默认关闭或未配置代替已完成。']}
    corrected=[v for stage in catalog.values() for v in stage['verification'] if v.get('archiveCorrection')]
    if corrected:
        assert len(corrected)==4,'Expected exactly four reconciliation corrections'
        result['archiveHashCorrections']=[v['archiveCorrection'] for v in corrected]
        result['source_artifacts']['reconciliationArchiveCorrection']={'path':ARCHIVE_CORRECTION,'sha256':sha(ROOT/ARCHIVE_CORRECTION)}
        result['limitations'].append('对账0792e22原4报告声明按LF预算、落盘CRLF；原字节未改。原声明不匹配明确保留，仅经追加更正及原record SHA/实际SHA/LF-normalized SHA三方精确校验匹配，不泛化允许漂移。')
    lines=['98项当前范围与剩余工作的证据审计','不是98项完成证明；当前任务状态照原表，不修改。','桥/售后最终冻结：'+str(result['finalIntegrationsFrozen']),'证据范围：冻结实施记录/报告，不代表生产渠道、生产部署或目标设备验收。']
    if corrected:lines.append('归档透明更正：对账4份原声明与实际CRLF字节SHA不符，已按精确原收据及追加更正验证；原声明/原文件保留。更正：'+ARCHIVE_CORRECTION+' SHA256='+sha(ROOT/ARCHIVE_CORRECTION))
    lines.append('')
    for r in rows:
        lines.extend([r['id']+' | '+r['task_table_status_at_audit']+' | '+r['title'],'原文：'+','.join(r['source_ids']),'当前声明范围：'+compact(r['declaredCurrentScope']),'尚未实现的软件：'+('；'.join(r['softwareNotImplemented']) or '本模板未新增断言；须按验收条款与证据scope核对，不据空列表认定完成。'),'外部输入：'+('；'.join(r['externalInputs']) or '参见原依赖（未自动归为外部）：'+r['unclassifiedDependencies']),'生产/目标验收：'+('；'.join(r['productionOrAcceptanceGates']) or '以当前实施记录限制和原验收条款为准。'),'冻结证据：'+'；'.join(x['path'] for x in r['evidence']),''])
    assert sha(TASKS)==before,'Task JSON changed during read; no audit written'
    if args.write:
        if args.replace_existing:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=OUT/('负责人优化建议-98项最终覆盖审计-更新前-'+stamp)
            old_json=AUDIT.read_bytes();old_txt=TEXT.read_bytes();bj=backup.with_suffix('.json');bt=backup.with_suffix('.txt')
            assert not bj.exists() and not bt.exists();assert hashlib.sha256(old_json).hexdigest()==result['source_artifacts']['previousAudit']['sha256']
            bj.write_bytes(old_json);bt.write_bytes(old_txt);assert bj.read_bytes()==old_json and bt.read_bytes()==old_txt
            result['source_artifacts']['previousAudit']['path']=str(bj.relative_to(ROOT)).replace('\\','/')
            result['source_artifacts']['previousAuditText']={'path':str(bt.relative_to(ROOT)).replace('\\','/'),'sha256':sha(bt)}
            dest=AUDIT;txt=TEXT
        else:
            dest=OUT/'负责人优化建议-98项最终覆盖审计-更新稿.json';txt=dest.with_suffix('.txt');assert not dest.exists() and not txt.exists(),'Review draft exists; preserve it before a new run'
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');txt.write_text('\n'.join(lines),encoding='utf-8')
        for artifact in result['source_artifacts'].values():assert sha(ROOT/artifact['path'])==artifact['sha256'],('Source artifact drift',artifact['path'])
        assert sha(TASKS)==before,'Task JSON changed during audit write'
    print(json.dumps({'mode':'replace-audit' if args.replace_existing else 'write-review-draft' if args.write else 'dry-run-read-only','taskCount':98,'evidenceRecords':len(catalog),'additionalFrozenRecordsValidated':len(additional),'finalIntegrationsFrozen':bool(bridge and sales),'taskJSONModified':False,'oldAuditOverwritten':args.replace_existing,'auditWritten':args.write},ensure_ascii=False))
if __name__=='__main__':main()
