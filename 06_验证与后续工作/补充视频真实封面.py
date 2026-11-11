from pathlib import Path
r=Path(__file__).resolve().parent.parent/'04_研发源码/app/r4';cloud=r.parent/'cloud'
p=r/'build.py';s=p.read_text(encoding='utf-8');needle="app='''<!doctype"
line="art_script+='const COMMUNITY_PREVIEW_POSTER='+json.dumps('data:image/jpeg;base64,'+base64.b64encode((ROOT/'images/community-preview-poster.jpg').read_bytes()).decode())+';'\n"
assert needle in s;s=s.replace(needle,line+needle,1);p.write_text(s,encoding='utf-8')
p=cloud/'prepare.py';s=p.read_text(encoding='utf-8');needle='const COMMUNITY_PREVIEW_VIDEO="/assets/community-preview.mp4";'
assert needle in s;s=s.replace(needle,needle+'const COMMUNITY_PREVIEW_POSTER="/assets/community-preview-poster.jpg";',1)
needle="shutil.copyfile(source/'images/community-preview.mp4',public/'assets/community-preview.mp4')";assert needle in s;s=s.replace(needle,needle+"\nshutil.copyfile(source/'images/community-preview-poster.jpg',public/'assets/community-preview-poster.jpg')",1);p.write_text(s,encoding='utf-8')
p=r/'community-feed.js';s=p.read_text(encoding='utf-8')
old="""'<video playsinline muted loop preload="metadata" src="'"""
new="""'<video playsinline muted loop preload="metadata"'+(preview?' poster="'+esc(COMMUNITY_PREVIEW_POSTER)+'"':'')+' src="'"""
assert old in s;s=s.replace(old,new,1);p.write_text(s,encoding='utf-8')
p=r.parents[2]/'06_验证与后续工作/Netlify本地联调服务.mjs';s=p.read_text(encoding='utf-8').replace("'.png':'image/png'","'.png':'image/png','.jpg':'image/jpeg'");p.write_text(s,encoding='utf-8')

