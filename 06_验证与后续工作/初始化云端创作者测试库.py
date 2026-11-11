"""Seed only a newly migrated checkout-local D1 fixture; never a production database."""
from pathlib import Path
import sys,re,json,sqlite3,hashlib,secrets,time
root=Path(__file__).resolve().parent.parent
cloud=root/'04_研发源码/app/cloud'
name=sys.argv[1] if len(sys.argv)==2 else ''
assert re.fullmatch(r'[a-z][a-z0-9]{0,4}',name), 'Use a short isolated runtime state name'
base=(cloud/'.wrangler'/name).resolve()
assert base.is_relative_to((cloud/'.wrangler').resolve())
files=[p for p in (base/'v3/d1').rglob('*.sqlite') if len(p.stem)==64]
assert len(files)==1,'Migrate a single local D1 database before seeding'
creds=json.loads((cloud/'.env.local-test').read_text(encoding='utf-8'))
salt=secrets.token_bytes(16);digest=salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',creds['password'].encode(),salt,100000).hex();stamp=int(time.time()*1000)
with sqlite3.connect(files[0]) as db:
 assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0,'Refuse to overwrite an existing test database'
 db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',('cloud-owner',creds['username'],digest,'Isolated admin','admin',stamp))
 for key,value in [('ai',{}),('theme',{}),('integrations',{}),('cloud_bootstrap_v1',True)]:db.execute('INSERT INTO settings VALUES (?,?)',(key,json.dumps(value)))
 for kind,items in json.loads((cloud/'generated/seed.json').read_text(encoding='utf-8')).items():
  for position,item in enumerate(items):db.execute('INSERT INTO contents VALUES (?,?,?,?,?,?)',(kind,item['id'],json.dumps(item,ensure_ascii=False),'published',position,stamp))
print('Seeded new isolated local D1 fixture. Credentials were not printed.')
