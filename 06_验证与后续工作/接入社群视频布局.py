from pathlib import Path
root=Path(__file__).resolve().parent.parent;r=root/'04_研发源码/app/r4'
p=r/'platform.js';s=p.read_text(encoding='utf-8')
a=s.index('function pxCommunity()');b=s.index('function pxPublish()',a);s=s[:a]+'function pxCommunity(){return communityFeedPage();}\n'+s[b:]
s=s.replace("pxTop(pxText('发布内容','Create a post'),pxText('提交审核后公开展示','Public after review'),'community')","pxTop(pxText('发布内容','Create a post'),pxText('提交审核后公开展示','Public after review'),'communityPosts')",1)
s=s.replace("if(state.page==='community'&&changed)","if(['community','communityPosts'].includes(state.page)&&changed)",1)
s=s.replace("if(id==='community')pxLoadFeed();","if(['community','communityPosts'].includes(id))pxLoadFeed();",1)
s=s.replace("px.tab='mine';px.draft={};navigate('community');","px.tab='mine';px.draft={};navigate('communityPosts');",1)
old="const source=pxProfileOriginal();return source.replace"
new="const source=pxProfileOriginal();return source.replace"
# Add a management entry under My profile, leaving only the requested three destinations in the community header.
needle='<div class="px-account-line"><span>'+chr(36)+"{icon('user')}"
replacement='<div class="px-account-line"><span>'+chr(36)+"{icon('video')}"+chr(36)+"{t('My videos & posts','我的视频与发布')}</span>"+chr(36)+"{go(t('View','查看'),'communityPosts','link')}</div>"+needle
assert needle in s;s=s.replace(needle,replacement,1)
s=s.replace(chr(36)+"{pxTop(pxText('我的好友','Friends'),'','community')}",chr(36)+"{communityHeader('friends')}",1)
s=s.replace(chr(36)+"{pxTop(pxText('我的对话','Messages'),'','community')}",chr(36)+"{communityHeader('communityInbox')}",1)
p.write_text(s,encoding='utf-8')
p=r/'build.py';s=p.read_text(encoding='utf-8').replace("'journey.js','i18n-ui.js'","'journey.js','community-feed.js','i18n-ui.js'").replace("'i18n.css','academy-teachers.css'","'i18n.css','academy-teachers.css','community-feed.css'");p.write_text(s,encoding='utf-8')
p=r/'homepage.js';s=p.read_text(encoding='utf-8').replace("['profile','growth','favorites'","['profile','communityPosts','publish','growth','favorites'");p.write_text(s,encoding='utf-8')
for name in ['全量回归.cjs','Netlify适配全量回归.cjs']:
 p=root/'06_验证与后续工作'/name;s=p.read_text(encoding='utf-8')
 s=s.replace("await go('community');await page.locator('.ew-teacher-entry').click();await page.waitForFunction(()=>state.page==='teachers');await go('community');await page.locator('.ew-community-tools [data-to=friends]').click();await page.waitForFunction(()=>['friends','account'].includes(state.page));","await go('community');assert.equal(await page.locator('.community-tabs button').count(),3);await page.locator('.community-tabs [data-to=friends]').click();await page.waitForFunction(()=>state.page==='friends');await page.locator('.community-tabs [data-to=communityInbox]').click();await page.waitForFunction(()=>state.page==='communityInbox');")
 s=s.replace("assert.equal(await page.locator('.ew-main-header').count(),1);","assert.equal(await page.locator(id==='community'?'.community-tabs':'.ew-main-header').count(),1);")
 s=s.replace("await page.locator('[data-action=px-feed-tab][data-tab=discover]').click();","")
 s=s.replace("await page.locator('[data-action=px-feed-tab][data-tab=mine]').click();","await go('communityPosts');")
 p.write_text(s,encoding='utf-8')
print('Community navigation, player lifecycle, profile management entry and regression routes connected.')

