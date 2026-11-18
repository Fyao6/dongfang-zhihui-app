"""Guarded apply/rollback only. Created for root; do not run before its module gate."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(v):return hashlib.sha256(v).hexdigest()
def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--apply',action='store_true');group.add_argument('--rollback',action='store_true');args=parser.parse_args()
    plan=json.loads((Path(__file__).with_name('负责人优化建议-分佣接入计划.json')).read_text(encoding='utf-8-sig'))
    for name,value in plan['newSourcePrerequisites'].items():
        assert sha((ROOT/name).read_bytes())==value,'CM freeze prerequisite changed: '+name
    originals={};candidates={};already=[]
    for f in plan['files']:
        file=(ROOT/f['path']).resolve();assert file.is_relative_to(ROOT.resolve()),'Outside root';raw=file.read_bytes();originals[file]=raw
        source_hash=f['afterSha256'] if args.rollback else f['beforeSha256'];target_hash=f['beforeSha256'] if args.rollback else f['afterSha256']
        if sha(raw)==target_hash:already.append(f['path']);continue
        assert sha(raw)==source_hash,'Before SHA changed; no files written: '+f['path']
        text=raw.decode('utf-8');ops=list(reversed(f['operations'])) if args.rollback else f['operations']
        for op in ops:
            anchor=op['replacement'] if args.rollback else op['anchor'];replacement=op['anchor'] if args.rollback else op['replacement']
            assert text.count(anchor)==op['expectedCount'],f['path']+' anchor '+op['label']
            text=text.replace(anchor,replacement)
        result=text.encode('utf-8');assert sha(result)==target_hash,'Candidate SHA mismatch: '+f['path'];candidates[file]=result
    # All files and every anchor are checked before the first source mutation.
    if args.apply or args.rollback:
        written=[]
        try:
            for file,data in candidates.items():file.write_bytes(data);written.append(file)
        except BaseException:
            for file in candidates:file.write_bytes(originals[file])
            raise
    print(json.dumps({'mode':'rollback' if args.rollback else 'apply' if args.apply else 'check-only','validatedFiles':len(plan['files']),'changedFiles':len(candidates) if args.apply or args.rollback else 0,'alreadyAtTarget':already,'buildExecuted':False,'databaseOpened':False},ensure_ascii=False))
if __name__=='__main__':main()
