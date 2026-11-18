"""Keep new module evidence separate and allow explicit isolated Cloud base URLs."""
from pathlib import Path
import re
Q=Path(__file__).resolve().parent
p=Q/'全量回归.cjs'
s=p.read_text(encoding='utf-8')
if 'const qaEvidenceName=' not in s:
 marker='const db='
 at=s.index(marker)
 s=s[:at]+"const qaRequested=process.argv.find(x=>x.startsWith('--module='))?.slice(9)||'';const qaEvidenceName=name=>qaRequested.startsWith('负责人优化建议')?qaRequested+'-'+name:name;\n"+s[at:]
 s=re.sub(r"path\.join\(__dirname,'([^']+\.(?:png|webm|json))'\)",lambda m:"path.join(__dirname,qaEvidenceName('"+m[1]+"'))",s)
 p.write_text(s,encoding='utf-8')
p=Q/'准备云端回归.py'
s=p.read_text(encoding='utf-8')
old="async function start(){base='http://127.0.0.1:8877';"
new="async function start(){base=process.argv.find(x=>x.startsWith('--base='))?.slice(7)||'http://127.0.0.1:8877';if(!/^http:\\\\/\\\\/(127[.]0[.]0[.]1|localhost):[0-9]+$/.test(base)||['8880','8879'].includes(new URL(base).port))throw Error('Isolated loopback only');"
if new not in s:
 assert s.count(old)==1
 s=s.replace(old,new,1)
 p.write_text(s,encoding='utf-8')
print('Module-specific full-regression evidence enabled; Cloud accepts an isolated --base.')
