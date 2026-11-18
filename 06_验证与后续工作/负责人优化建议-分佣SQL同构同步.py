"""Regenerate ONLY the marked shared SQL in the new commission Cloud adapter."""
import ast
import json
from pathlib import Path
import sqlite3
root=Path(__file__).resolve().parents[1]
py=root/'04_研发源码/app/r4/backend/commission.py'
ts=root/'04_研发源码/app/cloud/lib/commission-api.ts'
constants={}
for n in ast.parse(py.read_text(encoding='utf-8')).body:
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('DDL','SNAPSHOT_SQL'):
        constants[n.targets[0].id]=ast.literal_eval(n.value)
statements=[]; current=''
for line in constants['DDL'].splitlines():
    current+=line+'\n'
    if sqlite3.complete_statement(current):
        statements.append(current.strip());current=''
assert not current.strip()
source=ts.read_text(encoding='utf-8');start='/* SHARED_SQL_START */';end='/* SHARED_SQL_END */'
replacement=start+'\nconst DDL:string[]='+json.dumps(statements,ensure_ascii=False)+';\nexport const COMMISSION_SNAPSHOT_SQL='+json.dumps(constants['SNAPSHOT_SQL'],ensure_ascii=False)+';\n'+end
source=source[:source.index(start)]+replacement+source[source.index(end)+len(end):]
ts.write_text(source,encoding='utf-8');print(json.dumps({'sameSqlStatements':len(statements)}))
