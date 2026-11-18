"""Independent stage29 execution inventory; no services or artifact authors are started.

The reviewed launcher inputs are explicit.  The old freezer is imported only for
its read-only required_identity_paths(), never collect()/freeze().  Generator
inputs are reported separately and are not falsely called executed QA inputs.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import ast
import importlib.util
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-卡组迁移'
NODE = Path('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
QA_FILES = ('测试工具.cjs', '验收启动.cjs', '用例工具.cjs', '专项.cjs', '导入专项.cjs', '版本专项.cjs', '归档专项.cjs', '原生专项.cjs', '补充视觉.cjs', '入口预检.cjs', '入口清单.json', '验收计划.json', '夹具.json', 'Python测试服务.py', 'Cloud测试服务.ts', '夹具控制.py', '夹具控制.ts', '隐私夹具控制.py', '隐私夹具控制.ts', 'HTTP流式夹具.py', '抽卡兼容.cjs', 'B11兼容.cjs', 'B11浏览器兼容.cjs', '注销兼容.cjs', '注销兼容测试工具.cjs', '注销兼容Python测试服务.py', '注销兼容Cloud测试服务.ts', '脱敏前置.cjs')
FIXED_INPUTS = ('06_验证与后续工作/负责人优化建议-卡组迁移-执行合同.json', '06_验证与后续工作/负责人优化建议-卡组导入迁移-接口合同.json', '06_验证与后续工作/负责人优化建议-抽卡专项.cjs', '06_验证与后续工作/负责人优化建议-抽卡测试工具.cjs', '06_验证与后续工作/负责人优化建议-抽卡Python测试服务.py', '06_验证与后续工作/负责人优化建议-抽卡Cloud测试服务.ts', '04_研发源码/app/r4/card-import-engine.js', '04_研发源码/app/r4/card-import-engine.d.ts', '04_研发源码/app/r4/backend/card_import_worker.cjs', '04_研发源码/app/r4/backend/card_import_wire.py', '04_研发源码/app/r4/backend/card_import_schema.sql', '04_研发源码/app/r4/backend/card_history_migration_schema.sql', '04_研发源码/app/cloud/generated/card-import-schema.sql', '04_研发源码/app/cloud/generated/card-history-migration-schema.sql', '02_需求与设计参考/方向样卡-P528原文待审核.txt', '02_需求与设计参考/卡组导入模板-方向原文待审核.json', '02_需求与设计参考/旧卡示例归档-文件格式模板.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_path(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), ('Missing fixed input', name)
    return path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def managed_paths():
    tree=ast.parse(local_path('04_研发源码/app/r4/build_bazi_sample_manifest.py').read_text(encoding='utf-8'))
    values=ast.literal_eval(next(node.value for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='MANAGED' for target in node.targets)))
    assert len(values)==len(set(values))==21,'Managed worker FS input count changed'
    return set(values)


def required_identity_paths():
    previous=load_module('stage29_readonly_declarations',OUT/'负责人优化建议-八字样本依赖盘点.py')
    paths=set(previous.required_identity_paths())
    paths.update('06_验证与后续工作/'+PREFIX+suffix for suffix in QA_FILES)
    paths.update(FIXED_INPUTS)
    # A separate AST walk: embedded UMD/data strings are not executable imports.
    # Actual child -e scripts, managed worker FS reads and other fixed bytes are
    # explicitly declared above. Do not run the frozen stage28 all-JS regex walk.
    script=r"""
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',b=>input+=b);process.stdin.on('end',()=>{
 const {root,seeds}=JSON.parse(input),ts=require(path.join(root,'04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js'));
 const files=new Set(seeds),queue=seeds.filter(n=>/\.(?:[cm]?js|[cm]?ts)$/.test(n)),seen=new Set();
 while(queue.length){const name=queue.shift();if(seen.has(name))continue;seen.add(name);const file=path.join(root,name);assert(fs.statSync(file).isFile());
  const tree=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,/\.(?:ts|mts|cts)$/.test(name)?ts.ScriptKind.TS:ts.ScriptKind.JS),imports=[];
  const literal=node=>node&&(ts.isStringLiteral(node)||ts.isNoSubstitutionTemplateLiteral(node));
  const visit=node=>{if((ts.isImportDeclaration(node)||ts.isExportDeclaration(node))&&literal(node.moduleSpecifier))imports.push(node.moduleSpecifier.text);
   if(ts.isCallExpression(node)&&node.arguments.length===1&&literal(node.arguments[0])&&((ts.isIdentifier(node.expression)&&node.expression.text==='require')||node.expression.kind===ts.SyntaxKind.ImportKeyword))imports.push(node.arguments[0].text);
   ts.forEachChild(node,visit);};visit(tree);
  for(const value of imports){if(!value.startsWith('.'))continue;const base=path.resolve(path.dirname(file),value.split('?')[0]),choices=[base,base.replace(/\.mjs$/,'.mts'),base.replace(/\.js$/,'.ts'),...['.cjs','.js','.mjs','.ts','.mts','.json','.html','.sql'].map(ext=>base+ext),...['index.cjs','index.js','index.ts'].map(n=>path.join(base,n))];
   const found=choices.find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());assert(found,'Unresolved real AST import: '+name+' -> '+value);const relative=path.relative(root,found).replaceAll('\\','/');assert(!relative.startsWith('../')&&!path.isAbsolute(relative));files.add(relative);if(/\.(?:[cm]?js|[cm]?ts)$/.test(relative))queue.push(relative);
  }
 }
 process.stdout.write(JSON.stringify([...files].sort()));
});
"""
    result=json.loads(subprocess.check_output([str(NODE),'-e',script],input=json.dumps({'root':str(ROOT),'seeds':sorted(paths)}),encoding='utf-8',cwd=ROOT))
    assert len(result)==len(set(result))
    for name in result:local_path(name)
    return set(result)


def build_preparation_paths():
    """Actual generator FS inputs, apart from files already in the execution map."""
    r4 = '04_研发源码/app/r4/'
    names = ['assets.json', 'build_i18n.py', 'i18n-bo.json', 'i18n-bo-draft.json', 'i18n-extra.json',
             'creator-center.html', 'review.html', 'vendor/iztro-LICENSE.txt', 'vendor/iztro-2.6.2.min.js',
             'vendor/opencc-cn2t-1.0.5.js', 'vendor/opencc-LICENSE.txt', 'vendor/opencc-data-LICENSE.txt',
             'vendor/lunar-1.7.7.js', 'vendor/lunar-1.7.7-LICENSE.txt',
             'vendor/astronomy-engine-2.1.19.min.js', 'vendor/astronomy-engine-LICENSE.txt',
             'vendor/NotoSerifTibetan-OFL.txt', 'images/quote-landscape.png', 'images/map-life.png',
             'images/map-body.png', 'images/map-mind.png', 'images/community-preview.mp4']
    paths = {r4 + name for name in names if (ROOT / r4 / name).is_file()}
    paths.add('06_验证与后续工作/四语文案清单.json')
    for name in ('package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.openai/hosting.json', 'db/schema.ts'):
        relative = '04_研发源码/app/cloud/' + name
        if (ROOT / relative).is_file():
            paths.add(relative)
    return paths


def runtime_compiler_paths():
    # These installed executable dependencies are deliberately not project source
    # or handoff contents, but the actual Cloud prebundle now reads/runs them.
    return {
        '04_研发源码/app/cloud/node_modules/esbuild/lib/main.js',
        '04_研发源码/app/cloud/node_modules/esbuild/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/esbuild.exe',
    }


def inventory():
    required = required_identity_paths()
    command = "const h=require('./06_验证与后续工作/负责人优化建议-卡组迁移测试工具.cjs');process.stdout.write(JSON.stringify({files:h.sourceFiles(),qaFiles:h.qaFiles,identity:h.identity(),preparation:h.buildPreparationInputs()}));"
    actual = json.loads(subprocess.check_output([str(NODE), '-e', command], cwd=ROOT, text=True, encoding='utf-8'))
    assert set(actual['qaFiles']) == set(QA_FILES) and len(actual['qaFiles']) == len(QA_FILES), 'Reviewed QA list drifted'
    assert len(actual['files']) == len(set(actual['files'])), 'Duplicate identity paths'
    missing = sorted(required - set(actual['files']))
    extra = sorted(set(actual['files']) - required)
    assert not missing and not extra, ('Independent/harness input inventory mismatch', missing, extra)
    mapping = {name: sha(local_path(name)) for name in sorted(required)}
    assert mapping == actual['identity'], 'Harness and independent hashes differ'
    managed={name:sha(local_path(name)) for name in sorted(managed_paths())}
    preparation=actual['preparation']
    assert preparation['workerFsInputHashes']=={n:sha(local_path(n)) for n in ['04_研发源码/app/r4/backend/card_import_worker.cjs','04_研发源码/app/r4/card-import-engine.js']}
    assert preparation['serverSchemaInputHashes']=={n:sha(local_path(n)) for n in ['04_研发源码/app/r4/backend/card_import_schema.sql','04_研发源码/app/r4/backend/card_history_migration_schema.sql','04_研发源码/app/cloud/generated/card-import-schema.sql','04_研发源码/app/cloud/generated/card-history-migration-schema.sql']}
    assert preparation['typeContractMetadataHashes']=={'04_研发源码/app/r4/card-import-engine.d.ts':sha(local_path('04_研发源码/app/r4/card-import-engine.d.ts'))}
    prior=preparation['priorBaziCompatibilityRead']
    assert prior['managedInputHashes']==managed and prior['generatorSha256']==sha(local_path('04_研发源码/app/r4/build_bazi_sample_manifest.py'))
    assert preparation['executedByThisSuite'] is False and prior['executedByThisSuite'] is False
    parser=actual['preparation']['identityReaderRuntime']
    assert parser['parser']=='typescript' and parser['sha256']==sha(local_path('04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js'))
    package=local_path('04_研发源码/app/cloud/node_modules/typescript/package.json')
    assert parser['packageSha256']==sha(package) and parser['version']==json.loads(package.read_text(encoding='utf-8'))['version']
    assert parser['toolchainIncludedInHandoff'] is False
    canonical = json.dumps(mapping, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    generator = {name: sha(local_path(name)) for name in sorted(build_preparation_paths() - required)}
    compiler = {name: sha(local_path(name)) for name in sorted(runtime_compiler_paths())}
    return {'at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'pass': True,
            'cardBuildPreparation':actual['preparation'],'nodeExecutable':{'path':str(NODE),'sha256':sha(NODE),'version':subprocess.check_output([str(NODE),'--version'],text=True).strip(),'includedInHandoff':False},
            'inputCount': len(mapping), 'sourceAndBuildHashes': mapping,
            'canonicalSHA256': hashlib.sha256(canonical).hexdigest(),
            'independentRequiredCount': len(required), 'harnessCount': len(actual['files']),
            'missingFromHarness': missing, 'harnessAdditional': extra,
            'explicitChildPreload': '06_验证与后续工作/' + PREFIX + '脱敏前置.cjs',
            'buildPreparationInputHashes': generator,
            'runtimeCompilerDependencyHashes': compiler,
            'runtimeCompilerBoundary': 'Four installed esbuild API/package/platform/binary inputs are bound separately from project execution inputs; node_modules is not included in handoff.',
            'boundary': 'Independent actual project source/build/QA execution inventory matched before gates. Generator-only FS inputs and four actual installed Cloud compiler dependencies are separately bound, without inflating the project input count or claiming each QA gate executes generator inputs. No service, test, freeze, progress update or workbook author is started.'}


if __name__ == '__main__':
    import sys
    result=inventory()
    flags=[arg.split('=',1)[1] for arg in sys.argv[1:] if arg.startswith('--snapshot=')]
    assert len(flags)<=1
    target=None
    if flags:
        name=flags[0];assert re.fullmatch(r'[A-Za-z0-9_-]{1,50}',name)
        target=OUT/(PREFIX+'-'+name+'完整依赖诊断.json');assert not target.exists(),'Never overwrite a pre-run snapshot'
        target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'inputCount':result['inputCount'],'canonicalSHA256':result['canonicalSHA256'],'report':str(target) if target else None,'readOnly':target is None},ensure_ascii=True))
