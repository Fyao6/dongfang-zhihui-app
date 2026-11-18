"""Default read-only source parity; --write changes only the owned new TS module. No imports/DB/service."""
from pathlib import Path
import argparse,ast,json,sqlite3
ROOT=Path(__file__).resolve().parents[1];PY=ROOT/'04_研发源码/app/r4/backend/secret_references.py';TS=ROOT/'04_研发源码/app/cloud/lib/secret-references.ts'
p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args()
tree=ast.parse(PY.read_text(encoding='utf-8'));ddl=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DDL' for x in n.targets));statements=[];buffer=''
for character in ddl:
    buffer+=character
    if sqlite3.complete_statement(buffer):
        if buffer.strip():statements.append(buffer.strip())
        buffer=''
assert not buffer.strip()
marker='// Shared static SQL is generated from the Python module by the owned preparation helper.'
raw=TS.read_bytes();text=raw.decode('utf-8');assert text.count(marker)==1
proposed=(text.split(marker)[0]+marker+'\nconst DDL:string[]='+json.dumps(statements,ensure_ascii=False)+';\n').encode()
if args.write and proposed!=raw:TS.write_bytes(proposed)
print(json.dumps({'mode':'write-owned-module' if args.write else 'read-only','statements':len(statements),'wouldChange':proposed!=raw,'sourceOnly':True,'databaseOpened':False,'serviceStarted':False}))
