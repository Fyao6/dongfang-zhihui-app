from pathlib import Path
q=Path(__file__).resolve().parent
for name in ['全量回归.cjs','Netlify适配全量回归.cjs']:
 p=q/name;s=p.read_text(encoding='utf-8')
 s=s.replace("await video.evaluate(v=>v.play());","await video.locator('..').locator('.cf-stage-toggle').click();")
 s=s.replace("await v.evaluate(v=>v.play());","await v.locator('..').locator('.cf-stage-toggle').click();")
 p.write_text(s,encoding='utf-8')

