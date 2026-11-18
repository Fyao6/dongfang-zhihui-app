"""Read-only UTF-8 byte-range plan; SQLite complete_statement never executes SQL."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-当前产品可靠性恢复-'
PHASES = {'PRAGMA': 0, 'CREATE TABLE': 1, 'INSERT INTO': 2,
          'CREATE INDEX': 3, 'CREATE UNIQUE INDEX': 3, 'CREATE VIEW': 4, 'CREATE TRIGGER': 5}
sha = lambda value: hashlib.sha256(value).hexdigest()


def make_plan(file, expected):
    file = Path(file).resolve()
    assert file.parent == OUT and file.name.startswith(PREFIX) and file.suffix == '.sql'
    assert file.is_file() and not file.is_symlink()
    assert re.fullmatch('[a-f0-9]{64}', expected)
    raw = file.read_bytes()
    assert 0 < len(raw) <= 32 * 1024 * 1024 and sha(raw) == expected
    text = raw.decode('utf-8', 'strict')
    assert not text.startswith('\ufeff')
    pending, start, end, statements = '', 0, 0, []
    for line in text.splitlines(keepends=True):
        pending += line
        end += len(line.encode('utf-8'))
        if not sqlite3.complete_statement(pending):
            continue
        header = re.sub(r'^\s*(?:--[^\n]*\n\s*)*', '', pending)
        match = re.match(r'(?P<kind>CREATE (?:UNIQUE )?(?:TABLE|INDEX|VIEW|TRIGGER)|INSERT INTO|PRAGMA)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>`[^`]+`|"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)', header, re.I)
        assert match, 'unsupported exported statement type'
        kind, name = match['kind'].upper(), match['name'].strip('`"')
        assert kind in PHASES
        if kind == 'PRAGMA':
            assert re.fullmatch(r'PRAGMA\s+defer_foreign_keys\s*=\s*(?:TRUE|1)\s*;', header.strip(), re.I), 'only original defer_foreign_keys pragma is admitted'
            assert name.lower() == 'defer_foreign_keys'
        else:
            assert not name.startswith(('_cf_', 'sqlite_')), 'platform/internal statements refused'
        data = raw[start:end]
        assert data.decode('utf-8') == pending
        statements.append({'index': len(statements), 'startByte': start, 'endByte': end,
                           'lengthBytes': end - start, 'sha256': sha(data), 'kind': kind,
                           'name': name, 'phase': PHASES[kind]})
        pending, start = '', end
    assert not pending.strip(), 'incomplete trailing SQL'
    if start != len(raw):
        assert statements and raw[start:].decode('utf-8').strip() == ''
        last = statements[-1]
        last['endByte'], last['lengthBytes'] = len(raw), len(raw) - last['startByte']
        last['sha256'] = sha(raw[last['startByte']:])
    assert statements and len(statements) <= 10000
    assert statements[0]['kind'] == 'PRAGMA' and sum(v['kind'] == 'PRAGMA' for v in statements) == 1
    assert sum(v['lengthBytes'] for v in statements) == len(raw)
    order = sorted(range(len(statements)), key=lambda i: (statements[i]['phase'], i))
    return {'schemaVersion': 1, 'operation': 'native-d1-sql-restore-plan',
            'source': {'path': file.relative_to(ROOT).as_posix(), 'sha256': expected, 'bytes': len(raw)},
            'parser': 'sqlite3.complete_statement', 'sqliteVersion': sqlite3.sqlite_version,
            'executesSQL': False, 'containsSqlText': False, 'sqlTokensModified': False,
            'allOriginalByteRangesPreserved': True, 'statements': statements, 'executionOrder': order,
            'orderPolicy': 'original defer FK; all tables; original data; indexes; views; complete triggers; stable order within each phase'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sql')
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    if not args.sql and not args.expected_sha256:
        print(json.dumps({'status': 'prepared-not-run', 'executesSQL': False}))
    else:
        assert args.sql and args.expected_sha256
        print(json.dumps(make_plan(args.sql, args.expected_sha256), ensure_ascii=False, separators=(',', ':')))
