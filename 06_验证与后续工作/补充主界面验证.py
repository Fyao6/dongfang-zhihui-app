from pathlib import Path
p=Path(__file__).resolve().parent;f=p/'全量回归.cjs';s=f.read_text(encoding='utf-8-sig');i=s.index("await step(")
t='''await step('统一主界面实际入口与窄屏控件',async()=>{
 await go('academy');await page.locator('.ew-learning-intro [data-action=academy-filter]').click();assert.equal(await page.evaluate(()=>state.academyFilters.format),'practice');assert(await page.evaluate(()=>academyResults().every(x=>x.format==='practice')));await page.evaluate(()=>{state.academyFilters={theme:'all',access:'all',format:'all',query:''};render(false);});
 await go('community');await page.locator('.ew-teacher-entry').click();await page.waitForFunction(()=>state.page==='teachers');await go('community');await page.locator('.ew-community-tools [data-to=friends]').click();await page.waitForFunction(()=>['friends','account'].includes(state.page));
 for(const id of ['academy','service','community','profile']){await page.setViewportSize({width:360,height:740});await go(id);assert.equal(await page.locator('.ew-main-header').count(),1);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const bad=await page.locator('.ew-main-header,.ew-ai-suggestions button,.ew-teacher-entry,.profile-summary').evaluateAll(es=>es.some(e=>{const r=e.getBoundingClientRect();return r.left<0||r.right>innerWidth+1}));assert(!bad,'Primary controls fit the narrow viewport');}
 await page.setViewportSize({width:390,height:844});await go('home');
});
'''
s=s[:i]+t+s[i:];f.write_text(s,encoding='utf-8')
