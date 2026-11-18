"""Idempotent, narrowly scoped integration. Default prepares a plan; --apply is root's later step."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PYTHON = '04_研发源码/app/r4/backend/privacy.py'
CLOUD = '04_研发源码/app/cloud/lib/privacy-api.ts'
MARKER = 'privacy-gateway-bridge:v1'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def python_functions(text):
    tree = ast.parse(text)
    return {node.name: ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ('actual_binding', 'authorize_ai', 'save_conversation')}


def cloud_legacy(text):
    return {
        'actualBinding': text[text.index('async function actualBinding('):text.index('const disclosure=')],
        'authorizeAI': text[text.index('export async function authorizeAI('):text.index('export async function savePrivacyConversation(')],
        'savePrivacyConversation': text[text.index('export async function savePrivacyConversation('):text.index('export async function privacyRoute(')],
    }


def transform_python(text):
    if MARKER in text:
        assert text.count('_privacy_global_binding(cfg, self.store.setting(\'ai\'), self.store.setting(\'ai_gateway\'), actual_binding)') == 3
        return text, []
    before = python_functions(text)
    newline = '\r\n' if '\r\n' in text else '\n'
    anchor = 'from uuid import uuid4'
    assert text.count(anchor) == 1
    block = '''# privacy-gateway-bridge:v1: global disclosure only; legacy authorize/save stay actual_binding.
try:
    from privacy_gateway_bridge import global_binding as _privacy_global_binding
except ModuleNotFoundError:
    import importlib.util as _privacy_bridge_import
    from pathlib import Path as _PrivacyBridgePath
    _privacy_bridge_spec = _privacy_bridge_import.spec_from_file_location('eastern_privacy_gateway_bridge', _PrivacyBridgePath(__file__).with_name('privacy_gateway_bridge.py'))
    _privacy_bridge_module = _privacy_bridge_import.module_from_spec(_privacy_bridge_spec)
    _privacy_bridge_spec.loader.exec_module(_privacy_bridge_module)
    _privacy_global_binding = _privacy_bridge_module.global_binding'''.replace('\n', newline)
    changed = text.replace(anchor, anchor + newline + block, 1)
    old = "binding = actual_binding(cfg, self.store.setting('ai'))"
    new = "binding = _privacy_global_binding(cfg, self.store.setting('ai'), self.store.setting('ai_gateway'), actual_binding)"
    assert changed.count(old) == 3, 'Only public_config, response and preferences PATCH may change'
    positions = [{'lineBefore': text[:p].count('\n') + 1, 'before': old, 'after': new} for p in (i for i in range(len(text)) if text.startswith(old, i))]
    changed = changed.replace(old, new)
    assert python_functions(changed) == before, 'Legacy actual_binding/authorize_ai/save_conversation must remain byte-semantic unchanged'
    return changed, positions


def transform_cloud(text):
    if MARKER in text:
        assert text.count('privacyGlobalBinding(') == 4
        return text, []
    before = cloud_legacy(text)
    newline = '\r\n' if '\r\n' in text else '\n'
    imported = "// privacy-gateway-bridge:v1: global disclosure only; legacy authorize/save stay actualBinding." + newline + "import {globalBinding as privacyGlobalBinding} from './privacy-gateway-bridge';" + newline
    replacements = [
        ("const response=async()=>{const p=await prefs(a,uid),c=await configuration(a),b=await actualBinding(c,await a.setting('ai')),ack=", "const response=async()=>{const p=await prefs(a,uid),c=await configuration(a),b=await privacyGlobalBinding(c,await a.setting('ai'),await a.setting('ai_gateway'),actualBinding),ack="),
        ("return {config:disclosure(c,await actualBinding(c,await a.setting('ai')))};", "return {config:disclosure(c,await privacyGlobalBinding(c,await a.setting('ai'),await a.setting('ai_gateway'),actualBinding))};"),
        ("return {config:disclosure(clean,await actualBinding(clean,await a.setting('ai')))};", "return {config:disclosure(clean,await privacyGlobalBinding(clean,await a.setting('ai'),await a.setting('ai_gateway'),actualBinding))};"),
        ("p=await prefs(a,uid),binding=await actualBinding(c,await a.setting('ai'));let changes=", "p=await prefs(a,uid),binding=await privacyGlobalBinding(c,await a.setting('ai'),await a.setting('ai_gateway'),actualBinding);let changes="),
    ]
    positions = []
    changed = text
    for old, new in replacements:
        assert changed.count(old) == 1, 'Expected exact frozen privacy statement: ' + old
        positions.append({'lineBefore': text[:text.index(old)].count('\n') + 1, 'before': old, 'after': new})
        changed = changed.replace(old, new, 1)
    changed = imported + changed
    assert cloud_legacy(changed) == before, 'Legacy actualBinding/authorizeAI/savePrivacyConversation must remain byte-identical'
    return changed, positions


def prepare(root=ROOT):
    planned = {}
    for name, transform in ((PYTHON, transform_python), (CLOUD, transform_cloud)):
        current = (root / name).read_bytes().decode('utf-8')
        updated, locations = transform(current)
        planned[name] = {'current': current, 'updated': updated, 'beforeSha256': sha(current), 'afterSha256': sha(updated), 'alreadyApplied': current == updated, 'locations': locations}
    return planned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    planned = prepare()
    # Both transformations and legacy-preservation assertions succeed before either source is written.
    if args.apply:
        for name, p in planned.items():
            if not p['alreadyApplied']:
                assert (ROOT / name).read_bytes().decode('utf-8') == p['current'], 'Source changed after planning'
        for name, p in planned.items():
            if not p['alreadyApplied']:
                (ROOT / name).write_bytes(p['updated'].encode('utf-8'))
        assert all(p['alreadyApplied'] for p in prepare().values()), 'Integration must be idempotent'
    helper_names = ['04_研发源码/app/r4/backend/privacy_gateway_bridge.py', '04_研发源码/app/cloud/lib/privacy-gateway-bridge.ts']
    report = {'at': datetime.now(timezone.utc).isoformat(), 'applied': args.apply, 'scope': 'Only two privacy files; global disclosure binding and preferences. No gateway receipts or legacy outbound gate changes.', 'legacyOutboundUnchanged': True, 'helperHashes': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in helper_names}, 'files': {name: {k: v for k, v in p.items() if k not in ('current', 'updated')} for name, p in planned.items()}}
    report_path = ROOT / '06_验证与后续工作/负责人优化建议-AI隐私桥接接入计划.json'
    history = json.loads(report_path.read_text(encoding='utf-8')).get('runs', []) if report_path.exists() else []
    history.append(report)
    report_path.write_text(json.dumps({'latest': report, 'runs': history}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'applied': args.apply, 'files': {k: {'alreadyApplied': v['alreadyApplied'], 'changes': len(v['locations'])} for k, v in planned.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
