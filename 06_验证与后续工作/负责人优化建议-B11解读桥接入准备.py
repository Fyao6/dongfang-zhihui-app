"""Idempotent bridge build-list integration. Dry-run by default; no build/service/database execution."""
from pathlib import Path
import argparse
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / '04_研发源码/app/r4'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    target = R4 / 'build.py'
    before = target.read_text(encoding='utf-8')
    ast.parse(before)
    bridge = 'bazi-interpretation-bridge.js'
    anchor = "'bazi-result-version-release.js'"
    if before.count(anchor) != 1:
        raise SystemExit('Expected exactly one final B11 release build-list anchor')
    existing = before.count(repr(bridge))
    if existing > 1:
        raise SystemExit('Duplicate bridge build entry')
    after = before if existing else before.replace(anchor, anchor + ',' + repr(bridge), 1)
    if existing and anchor + ',' + repr(bridge) not in before:
        raise SystemExit('Bridge must follow the final release initializer, after every AI wrapper')
    tree = ast.parse(after)
    lists = [node for node in ast.walk(tree) if isinstance(node, ast.List) and any(isinstance(x, ast.Constant) and x.value == bridge for x in node.elts)]
    if len(lists) != 1:
        raise SystemExit('Bridge must occur in exactly one static JavaScript build list')
    values = [node.value for node in lists[0].elts if isinstance(node, ast.Constant)]
    if values[-2:] != ['bazi-result-version-release.js', bridge]:
        raise SystemExit('Expected release and bridge as the last two scripts')
    source = R4 / bridge
    if not source.is_file():
        raise SystemExit('Missing bridge source')
    report = {'mode': 'apply' if args.apply else 'dry-run', 'target': str(target.relative_to(ROOT)), 'wouldChange': after != before,
              'bridgeSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'allAnchorsUnique': True, 'wholeFileASTValid': True,
              'frozenB11FourSourcesChanged': False, 'sharedAIClientChanged': False, 'buildExecuted': False, 'serviceStarted': False}
    if args.apply and after != before:
        target.write_text(after, encoding='utf-8', newline='')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
