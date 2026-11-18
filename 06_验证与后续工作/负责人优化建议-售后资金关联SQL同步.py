"""Default read-only comparison of finance SQL constants; --write updates only the new owned Cloud module."""
from pathlib import Path
import argparse
import ast
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '04_研发源码/app/r4/backend/after_sales_finance.py'
CLOUD = ROOT / '04_研发源码/app/cloud/lib/after-sales-finance.ts'
MARKER = '// Shared SQL statements generated from the Python module by the preparation helper; no runtime source loading.'

def constants():
    tree = ast.parse(PYTHON.read_text(encoding='utf-8'))
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('DDL', 'READ_CASE_SQL', 'EVENTS_SQL')}
    statements, buffer = [], ''
    for line in values['DDL'].splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ''
    assert not buffer.strip(), 'Incomplete SQL statement'
    return statements, values

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    statements, values = constants()
    before = CLOUD.read_text(encoding='utf-8')
    assert before.count(MARKER) == 1
    after = before.split(MARKER)[0] + MARKER + '\nconst DDL:string[]=' + json.dumps(statements, ensure_ascii=False) + ';\n' + '\n'.join('const ' + key + '=' + json.dumps(values[key], ensure_ascii=False) + ';' for key in ('READ_CASE_SQL', 'EVENTS_SQL')) + '\n'
    if args.write and after != before:
        CLOUD.write_bytes(after.encode('utf-8'))
    print(json.dumps({'mode': 'write-owned-module' if args.write else 'read-only', 'statements': len(statements), 'wouldChange': before != after, 'sourceOnly': True, 'databaseOpened': False, 'sharedEntryChanged': False}))

if __name__ == '__main__':
    main()
