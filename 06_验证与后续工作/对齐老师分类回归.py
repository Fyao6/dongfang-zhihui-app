from pathlib import Path
r=Path(__file__).resolve().parent
for name in ['全量回归.cjs','Netlify适配全量回归.cjs']:
 p=r/name;s=p.read_text(encoding='utf-8');s=s.replace("await p.locator('#academy-search').fill(course.zh);await p.locator('[data-action=academy-open]", "await p.locator('#academy-search').fill(course.zh);await p.locator('[data-action=at-view][data-view=courses]').click();await p.locator('[data-action=academy-open]");p.write_text(s,encoding='utf-8')

