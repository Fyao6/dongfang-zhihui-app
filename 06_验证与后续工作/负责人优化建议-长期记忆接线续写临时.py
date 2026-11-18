from pathlib import Path
from difflib import SequenceMatcher
root=Path('04_研发源码/app')
def update(relative,pairs):
    path=root/relative
    old=path.read_bytes().decode('utf-8')
    s=old.replace('\r\n','\n')
    for a,b in pairs:
        if s.count(a)!=1:raise ValueError((relative,a[:140],s.count(a)))
        s=s.replace(a,b)
    old_lines=old.splitlines(keepends=True)
    current=s.splitlines(keepends=True)
    normalized=[line.replace('\r\n','\n') for line in old_lines]
    ending='\r\n' if old.count('\r\n')>old.count('\n')/2 else '\n'
    out=[]
    for tag,a,b,c,d in SequenceMatcher(None,normalized,current,autojunk=False).get_opcodes():
        out.extend(old_lines[a:b] if tag=='equal' else [line.replace('\n',ending) for line in current[c:d]])
    path.write_bytes(''.join(out).encode('utf-8'))

update('r4/backend/memory_service.py',[
 ('def public_memory_state(store,owner,prefs):','def public_memory_state(store,owner,prefs,*,include_count=True):'),
 ("count=db.execute('SELECT count(*) FROM memory_entries WHERE owner=?',(owner,)).fetchone()[0]", "count=db.execute('SELECT count(*) FROM memory_entries WHERE owner=?',(owner,)).fetchone()[0] if include_count else None"),
])
update('r4/backend/privacy.py',[
 ('public_memory_state(self.store,self.uid,p)','public_memory_state(self.store,self.uid,p,include_count=False)'),
])
update('cloud/lib/memory-service.ts',[
 ('publicMemoryState(a:any,owner:string,prefs:any)', 'publicMemoryState(a:any,owner:string,prefs:any,includeCount=true)'),
 ("storedCount:(await a.one('SELECT count(*) n FROM memory_entries WHERE owner=?',owner)).n","storedCount:includeCount?(await a.one('SELECT count(*) n FROM memory_entries WHERE owner=?',owner)).n:null"),
])
update('cloud/lib/privacy-api.ts',[
 ('await publicMemoryState(a,uid,p)','await publicMemoryState(a,uid,p,false)'),
])
update('r4/backend/privacy_retention.py',[
 ("'memoryStatus': 'completed', 'retainedCategories'","'memoryStatus': 'service-not-implemented', 'retainedCategories'"),
 ("set(data['retentionDays']) != set(SCOPES[2:])","set(data['retentionDays']) not in (set(SCOPES[2:]),set(SCOPES[2:-1]))"),
 ("'retentionDays':data['retentionDays']","'retentionDays':{'memory':old.get('retentionDays',{}).get('memory'),**data['retentionDays']}"),
])
update('cloud/lib/privacy-retention.ts',[
 ("!exact(d.retentionDays,RETENTION_SCOPES.slice(2))", "(!exact(d.retentionDays,RETENTION_SCOPES.slice(2))&&!exact(d.retentionDays,RETENTION_SCOPES.slice(2,-1)))"),
 ("retentionDays:d.retentionDays","retentionDays:{memory:old.retentionDays?.memory??null,...d.retentionDays}"),
])
