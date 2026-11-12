"""Publish only the existing, self-contained owner preview; never rebuild the APP."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, os, re, subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / '03_当前APP/发给负责人-东方智慧首页R4.html'
APP = ROOT / '03_当前APP/东方智慧-首页体验R4.html'
ADAPTER = ROOT / '06_验证与后续工作/GitHub静态预览提示.js'

def digest(data): return hashlib.sha256(data).hexdigest()

def prepare(output, commit=None):
    output = output.resolve()
    allowed = [(ROOT / '.git').resolve()]
    if os.environ.get('RUNNER_TEMP'): allowed.append(Path(os.environ['RUNNER_TEMP']).resolve())
    if not any(output.is_relative_to(base) and output != base for base in allowed):
        raise ValueError('Output must be a child of .git or the GitHub runner temporary directory')
    source = SOURCE.read_bytes()
    if not all(marker in source for marker in [b'preview.srcdoc=APP.replace', b'backend:location.protocol', b"const APP="]):
        raise ValueError('The self-contained owner preview contract changed; review before publishing')
    if not commit:
        commit = os.environ.get('GITHUB_SHA')
    if not commit:
        bundled = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
        command = str(bundled) if bundled.is_file() else 'git'
        commit = subprocess.run([command,'rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit): raise ValueError('Expected a full Git commit SHA')
    output.mkdir(parents=True,exist_ok=True)
    if any(p.name not in {'index.html','version.json','.nojekyll','pages-preview.js'} or not p.is_file() or p.is_symlink() for p in output.iterdir()):
        raise ValueError('Output contains unexpected files; no cleanup was attempted')
    # Use the last closing body: the embedded APP string also contains </body>.
    marker = b'<script src="./pages-preview.js"></script>'
    before, separator, after = source.rpartition(b'</body>')
    if not separator: raise ValueError('Owner preview closing body is missing')
    index = before + marker + separator + after
    adapter = ADAPTER.read_bytes()
    (output/'index.html').write_bytes(index)
    (output/'pages-preview.js').write_bytes(adapter)
    (output/'.nojekyll').write_bytes(b'')
    version = {
        'title':'东方智慧APP · GitHub在线交互预览',
        'source_commit':commit,
        'prepared_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'source_page':SOURCE.relative_to(ROOT).as_posix(),
        'preview_sha256':digest(source),
        'index_sha256':digest(index),
        'adapter_sha256':digest(adapter),
        'app_sha256':digest(APP.read_bytes()),
        'preview_bytes':len(source),
        'scope':'Owner preview and embedded APP source bytes preserved; one outer script explains the static scope and blocks unavailable server links. Original guest mode is unchanged; no server, account, AI or production data is deployed.',
        'business_rebuilt':False,
    }
    (output/'version.json').write_text(json.dumps(version,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if (output/'index.html').read_bytes().replace(marker,b'',1)!=source: raise AssertionError('Published owner preview bytes changed beyond the outer adapter tag')
    print(json.dumps({'pass':True,'output':str(output),'files':['index.html','version.json','.nojekyll','pages-preview.js'],**version},ensure_ascii=False),flush=True)
    return version

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--commit')
    args=parser.parse_args()
    prepare(args.output,args.commit)
