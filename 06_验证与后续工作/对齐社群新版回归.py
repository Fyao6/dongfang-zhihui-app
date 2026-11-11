from pathlib import Path
import json
root=Path(__file__).resolve().parent.parent;r=root/'04_研发源码/app/r4';q=root/'06_验证与后续工作'
p=r/'i18n-extra.json';d=json.loads(p.read_text(encoding='utf-8'));d['全部课程']={'en':'All courses','bo':'སློབ་ཚན་ཚང་མ།'};p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=q/'老师与社群新增四语.json';d=json.loads(p.read_text(encoding='utf-8'));d['全部课程']={'en':'All courses','bo':'སློབ་ཚན་ཚང་མ།'};p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['全量回归.cjs','Netlify适配全量回归.cjs']:
 p=q/name;s=p.read_text(encoding='utf-8')
 s=s.replace("await up.evaluate(()=>navigate('community'));await up.locator('[data-action=px-publish]')", "await up.evaluate(()=>navigate('profile'));await up.locator('[data-to=communityPosts]').click();await up.locator('[data-action=px-publish]')")
 s=s.replace("assert.equal(await up.locator('body').getAttribute('data-page'),'community');","assert.equal(await up.locator('body').getAttribute('data-page'),'communityPosts');")
 s=s.replace("await up.locator('[data-action=px-feed-tab][data-tab=discover]').click();","await up.evaluate(()=>navigate('community'));")
 s=s.replace("up.locator('.px-post').filter","up.locator('.cf-video-card').filter")
 s=s.replace(".px-post:not(.community-preview-video) video",".cf-video-card:not(.community-preview-video) video")
 s=s.replace("document.querySelector('#app>.page')","document.querySelector('#app>.community-feed-page')")
 p.write_text(s,encoding='utf-8')
p=q/'四语专项联调.cjs';s=p.read_text(encoding='utf-8').replace("ap.locator('[data-nav=courses]')","ap.locator('.sidebar [data-nav=courses]')");p.write_text(s,encoding='utf-8')
p=q/'发布老师课程归属.cjs';s=p.read_text(encoding='utf-8').replace("(sources[s]||[s,'https://www.iztro.com/learn/basis'])","(sources[s]||(()=>{throw Error('Unknown legacy source: '+s)})())");p.write_text(s,encoding='utf-8')
print('Regression now uses My profile for video publishing and the vertical feed for playback; Tibetan All courses added.')

