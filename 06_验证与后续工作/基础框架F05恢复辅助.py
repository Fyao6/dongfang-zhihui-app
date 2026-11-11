"""SQLite backup/fingerprint helper. Runtime files are confined to cloud/.wrangler."""
from pathlib import Path
import argparse,hashlib,json,sqlite3

ROOT=Path(__file__).resolve().parent.parent
RUNTIME=(ROOT/'04_研发源码/app/cloud/.wrangler').resolve()
def checked(raw):
    p=Path(raw).resolve()
    if p==RUNTIME or not p.is_relative_to(RUNTIME):
        raise ValueError('Only checkout-local cloud/.wrangler database files are allowed')
    return p
def encoded(value):
    if isinstance(value,bytes):return {'sqliteBlobHex':value.hex()}
    return value
def stable(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def connection(p,mode):
    return sqlite3.connect(p.as_uri()+'?mode='+mode,uri=True)
def fingerprint(raw):
    p=checked(raw)
    if not p.is_file():raise ValueError('Database does not exist')
    with connection(p,'ro') as db:
        integrity=[r[0] for r in db.execute('PRAGMA integrity_check')]
        tables={}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if name.startswith(('sqlite_','_cf_')):continue
            quoted='"'+name.replace('"','""')+'"'
            schema={'columns':[list(r) for r in db.execute('PRAGMA table_info('+quoted+')')],
                    'foreignKeys':[list(r) for r in db.execute('PRAGMA foreign_key_list('+quoted+')')]}
            schema['indexes']=[]
            for row in db.execute('PRAGMA index_list('+quoted+')'):
                index=row[1];iq='"'+index.replace('"','""')+'"'
                schema['indexes'].append({'name':index,'unique':row[2],'origin':row[3],
                    'partial':row[4],'columns':[list(r) for r in db.execute('PRAGMA index_info('+iq+')')]})
            schema['indexes'].sort(key=lambda r:r['name'])
            rows=sorted(stable([encoded(v) for v in row]) for row in db.execute('SELECT * FROM '+quoted))
            tables[name]={'rows':len(rows),'dataSha256':hashlib.sha256('\n'.join(rows).encode()).hexdigest(),
                'schemaSha256':hashlib.sha256(stable(schema).encode()).hexdigest()}
        return {'integrity':integrity,'foreignKeyViolations':len(list(db.execute('PRAGMA foreign_key_check'))),
                'journalMode':db.execute('PRAGMA journal_mode').fetchone()[0],
                'tables':tables,'fileSha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def backup(src,dst):
    a,b=checked(src),checked(dst)
    if not a.is_file() or a==b or b.exists():raise ValueError('Backup requires existing source and fresh distinct target')
    b.parent.mkdir(parents=True,exist_ok=True)
    with connection(a,'ro') as source,connection(b,'rwc') as target:
        source.backup(target)
        # Prepare the fresh backed-up file for the D1 WAL convention before placement.
        # This operation occurs at a short temporary filename, with no Windows global changes.
        target.execute('PRAGMA journal_mode=WAL')
        target.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return {'operation':'sqlite3.Connection.backup','target':fingerprint(b)}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['backup','fingerprint']);parser.add_argument('source');parser.add_argument('target',nargs='?')
    args=parser.parse_args()
    print(json.dumps(backup(args.source,args.target) if args.operation=='backup' else fingerprint(args.source),ensure_ascii=False))
