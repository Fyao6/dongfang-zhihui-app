from pathlib import Path
p=Path(__file__).resolve().parents[1];src=p/'04_研发源码/app/r4';f=src/'time-bank-admin.html';s=f.read_text(encoding='utf-8');s=s.replace("const texts=rows.map(r=>r.textContent.toLocaleLowerCase())", "const texts=rows.map(r=>(r.textContent+' '+[...r.querySelectorAll('[data-edit],[data-id]')].map(e=>e.dataset.edit||e.dataset.id).join(' ')).toLocaleLowerCase())");f.write_text(s,encoding='utf-8')
f=src/'build.py';s=f.read_text(encoding='utf-8').replace('import json,base64,shutil,subprocess','import json,base64,shutil,subprocess,re');a=s.index('if node:\n');b=s.index('art_script=',a)
s=s[:a]+'''admin_source=(ROOT/'time-bank-admin.html').read_text(encoding='utf-8')
if node:
 scripts=[('APP',js)]+[('ADMIN',part) for part in re.findall(r'<script>([\\s\\S]*?)</script>',admin_source)]
 for label,script in scripts:
  check=subprocess.run([node,'--check'],input=script,encoding='utf-8',capture_output=True)
  if check.returncode:
   raise RuntimeError(label+' JavaScript syntax check failed; current viewing pages were not overwritten.\\n'+check.stderr)
'''+s[b:]
s=s.replace("admin=(ROOT/'time-bank-admin.html').read_text(encoding='utf-8').replace('__SNAPSHOT__','null')", "admin=admin_source.replace('__SNAPSHOT__','null')");f.write_text(s,encoding='utf-8')
f=p/'06_验证与后续工作/全量回归.cjs';s=f.read_text(encoding='utf-8');old="await ap.locator('[data-list-search]').fill('');assert(await ap.locator('tbody tr:visible').count()>0);";new="await ap.locator('[data-list-search]').fill('');assert(await ap.locator('tbody tr:visible').count()>0);const contentId=await ap.locator('[data-edit]').first().getAttribute('data-edit');await ap.locator('[data-list-search]').fill(contentId);assert.equal(await ap.locator('tbody tr:visible').count(),1);await ap.locator('[data-list-search]').fill('');";assert old in s;s=s.replace(old,new);f.write_text(s,encoding='utf-8');print('Added ID lookup and build-time admin syntax validation.')
