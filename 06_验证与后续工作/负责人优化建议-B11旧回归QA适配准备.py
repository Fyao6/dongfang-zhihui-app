"""Prepared B11-only conditional QA update. Default read-only; --apply writes one existing QA file only."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    plan=json.loads((ROOT/'06_验证与后续工作/负责人优化建议-B11旧回归QA适配补丁.json').read_text(encoding='utf-8'))
    target=(ROOT/plan['target']).resolve()
    assert target.is_relative_to(ROOT/'06_验证与后续工作') and target.name=='八字体验逐模块验收.cjs'
    old=target.read_text(encoding='utf-8')
    if all(block['new'] in old for block in plan['blocks']):
        print(json.dumps({'mode':'apply' if args.apply else 'dry-run','alreadyApplied':True,'changed':False}));return
    if hashlib.sha256(target.read_bytes()).hexdigest()!=plan['base_sha256']:
        raise SystemExit('QA source changed since review; rebase exact replacements explicitly.')
    new=old
    for block in plan['blocks']:
        if new.count(block['old'])!=1:raise SystemExit('Patch anchor changed: '+block['name'])
        new=new.replace(block['old'],block['new'],1)
    if hashlib.sha256(new.encode()).hexdigest()!=plan['proposed_sha256']:raise SystemExit('Proposed QA digest mismatch')
    if args.apply:target.write_text(new,encoding='utf-8',newline='')
    print(json.dumps({'mode':'apply' if args.apply else 'dry-run','wouldChange':new!=old,'applied':bool(args.apply),'businessChanged':False,'testsExecuted':False,'target':plan['target']},ensure_ascii=False))
if __name__=='__main__':main()

