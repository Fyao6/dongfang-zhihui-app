"""Independent repair regression inventory. Default/import never starts a service.

Inherited frozen declarations are read-only. This reader has its own new fixed
list and AST traversal; it does not take the new harness list as its required set.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-本地可靠性Cloud复验'
NODE = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
QA_FILES = ('测试工具.cjs', '验收启动.cjs', '入口预检.cjs', '入口清单.json', '依赖盘点.py', '脱敏前置.cjs')
FIXED = ('负责人优化建议-本地可靠性Cloud复验授权基线-rev3.json',
         '负责人优化建议-本地可靠性Cloud复验修复基线.cjs', '负责人优化建议-本地可靠性-实施前核对.json',
         '负责人优化建议-卡组迁移-最终交付核验.json', '负责人优化建议-卡组迁移-实施记录.json',
         '负责人优化建议-卡组迁移依赖盘点.py', '负责人优化建议-八字样本依赖盘点.py',
         '负责人优化建议-支付路由依赖盘点.py', '负责人优化建议-任务告警依赖盘点.py',
         '负责人优化建议-隐私逐域验收冻结.py')



def sha(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def required_identity_paths():
    old = module('read_only_stage30_declarations', OUT / '负责人优化建议-卡组迁移依赖盘点.py')
    paths = set(old.required_identity_paths())
    paths.update('06_验证与后续工作/' + PREFIX + name for name in QA_FILES)
    paths.update('06_验证与后续工作/' + name for name in FIXED)
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / '04_研发源码/app/r4/backend').glob('*.py'))
    receipt = json.loads((OUT / '负责人优化建议-卡组迁移-实施记录.json').read_bytes())
    paths.update(gate['path'] for gate in receipt['verification'].values())
    authorization = json.loads((OUT / '负责人优化建议-本地可靠性Cloud复验授权基线-rev3.json').read_bytes())
    paths.update(value['originalBytes']['path'] for value in authorization['productChanges'].values() if value['originalBytes'])
    paths.update(authorization['currentExecutionBaseHashes'])
    before = json.loads((ROOT / authorization['cloudBeforeManifest']['path']).read_bytes())
    paths.update(value['originalBytes']['path'] for value in before['preserved'].values())
    paths.update(authorization[key]['path'] for key in ['cloudBeforeManifest', 'rootCandidateAnchor', 'previousRepairAuthorization', 'previousRepairProof'])
    script = r"""
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',s=>input+=s);process.stdin.on('end',()=>{
const {root,seeds}=JSON.parse(input),ts=require(path.join(root,'04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js'));
const files=new Set(seeds),queue=seeds.filter(n=>/\.(?:[cm]?js|[cm]?ts)$/.test(n)),seen=new Set(),literal=n=>n&&(ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n));
while(queue.length){const name=queue.shift();if(seen.has(name))continue;seen.add(name);const file=path.join(root,name);assert(fs.statSync(file).isFile());const tree=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,/\.[cm]?ts$/.test(name)?ts.ScriptKind.TS:ts.ScriptKind.JS),imports=[];
const visit=n=>{if((ts.isImportDeclaration(n)||ts.isExportDeclaration(n))&&literal(n.moduleSpecifier))imports.push(n.moduleSpecifier.text);if(ts.isCallExpression(n)&&n.arguments.length===1&&literal(n.arguments[0])&&((ts.isIdentifier(n.expression)&&n.expression.text==='require')||n.expression.kind===ts.SyntaxKind.ImportKeyword))imports.push(n.arguments[0].text);ts.forEachChild(n,visit);};visit(tree);
for(const spec of imports.filter(n=>n.startsWith('.'))){const base=path.resolve(path.dirname(file),spec.split('?')[0]),candidate=[base,base.replace(/\.mjs$/,'.mts'),base.replace(/\.js$/,'.ts'),...['.cjs','.js','.mjs','.ts','.mts','.json','.html','.sql'].map(x=>base+x)].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());assert(candidate,'Missing actual dependency '+name+' -> '+spec);const rel=path.relative(root,candidate).replaceAll('\\','/');assert(!rel.startsWith('../')&&!path.isAbsolute(rel));if(!files.has(rel)){files.add(rel);if(/\.(?:[cm]?js|[cm]?ts)$/.test(rel))queue.push(rel);}}
}process.stdout.write(JSON.stringify([...files].sort()));});
"""
    result = json.loads(subprocess.check_output([str(NODE), '-e', script],
                        input=json.dumps({'root': str(ROOT), 'seeds': sorted(paths)}),
                        encoding='utf-8', cwd=ROOT))
    assert len(result) == len(set(result))
    return set(result)


def inventory():
    required = required_identity_paths()
    command = "const h=require('./06_验证与后续工作/负责人优化建议-本地可靠性Cloud复验测试工具.cjs');process.stdout.write(JSON.stringify({files:h.sourceFiles(),identity:h.identity(),qaFiles:h.qaFiles,preparation:h.buildPreparationInputs()}));"
    actual = json.loads(subprocess.check_output([str(NODE), '-e', command], cwd=ROOT, encoding='utf-8'))
    assert set(actual['qaFiles']) == set(QA_FILES)
    missing, extra = sorted(required - set(actual['files'])), sorted(set(actual['files']) - required)
    assert not missing and not extra, (missing, extra)
    mapping = {name: sha(ROOT / name) for name in sorted(required)}
    assert mapping == actual['identity']
    parser = ROOT / '04_研发源码/app/cloud/node_modules/typescript'
    return {'pass': True, 'at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'stage': 31, 'inputCount': len(mapping), 'sourceAndBuildHashes': mapping,
            'canonicalSHA256': hashlib.sha256(json.dumps(mapping, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
            'missingFromHarness': missing, 'harnessAdditional': extra,
            'cardBuildPreparation': actual['preparation'],
            'identityReaderRuntime': {name: sha(parser / name) for name in ['lib/typescript.js', 'package.json']},
            'runtimeCompilerDependencyHashes': {name: sha(ROOT / name) for name in sorted(module('stage30_compiler_declarations', OUT / '负责人优化建议-卡组迁移依赖盘点.py').runtime_compiler_paths())},
            'boundary': 'Read-only execution/input inventory and metadata preparation only; no services, regression tests, load, database or workbook changes.'}


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print(json.dumps({'status': 'prepared-not-run', 'stage': 31, 'snapshotCreated': False,
                          'requiredNewQa': list(QA_FILES)}, ensure_ascii=False))
    else:
        assert len(sys.argv) == 2 and (sys.argv[1]=='--inspect' or sys.argv[1].startswith('--snapshot='))
        if sys.argv[1]=='--inspect':
            result=inventory()
            print(json.dumps({k:v for k,v in result.items() if k!='sourceAndBuildHashes'},ensure_ascii=False))
            sys.exit(0)
        name = sys.argv[1].split('=', 1)[1]
        assert name and all(c.isalnum() or c in '-_' for c in name)
        result = inventory()
        target = OUT / (PREFIX + '-' + name + '完整依赖诊断.json')
        with target.open('xb') as stream:
            stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({'pass': True, 'path': target.relative_to(ROOT).as_posix(), 'sha256': sha(target),
                          'inputCount': result['inputCount'], 'canonicalSHA256': result['canonicalSHA256']}, ensure_ascii=False))
