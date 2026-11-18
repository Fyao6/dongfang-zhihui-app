"""New rate contract check, isolated memory only; never overwrites the frozen lifecycle report."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
fixture=ROOT/'06_验证与后续工作/负责人优化建议-会员内存专项.py'
namespace={'__file__':str(fixture),'__name__':'membership_rate_fixture'}
exec(compile(fixture.read_text(encoding='utf-8').split('results=[]')[0],str(fixture),'exec'),namespace)
records=[]
for name in ('member','manager','other_member'):
    namespace[name].rate=lambda key,limit:records.append({'key':key,'limit':limit})
api=namespace['api'];Error=namespace['Error'];member=namespace['member'];manager=namespace['manager'];other=namespace['other_member']
api(member,namespace['user'],'/api/membership/status',method='GET')
try:api(member,namespace['user'],'/api/membership/restore',{'requestId':'rate-contract','environment':'production'})
except Error as e:assert e.status==403
api(other,namespace['other'],'/api/membership/status',method='GET')
api(manager,namespace['admin'],'/api/admin/membership',method='GET')
try:api(manager,namespace['admin'],'/api/admin/membership/settings',{'sandboxEnabled':True,'productionEnabled':True,'revision':0},'PATCH')
except Error as e:assert e.status==400
assert [x['limit'] for x in records]==[180,30,180,180,30]
assert records[0]['key']!=records[1]['key'] and records[0]['key']!=records[2]['key'] and records[3]['key']!=records[4]['key']
result={'kind':'isolated-new-rate-contract','pass':True,'readLimit':180,'writeLimit':30,'accountsIsolated':True,'readWriteBucketsDistinct':True,'observed':records,'productionDatabaseAccess':False,'oldMemoryReportsOverwritten':False}
(ROOT/'06_验证与后续工作/负责人优化建议-会员读写限频复核-python.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':True,'readLimit':180,'writeLimit':30,'accountsIsolated':True}))

