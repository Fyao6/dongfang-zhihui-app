// Homepage video cards share quotes, revisions and existing media storage.
const LANGUAGES=['zh','zh-Hant','en','bo'];
const TEXT_FIELDS=['zh','en','hant','bo','bannerLabel','bannerLabelEn','bannerLabelHant','bannerLabelBo','description','descriptionEn','descriptionHant','descriptionBo','buttonLabel','buttonLabelEn','buttonLabelHant','buttonLabelBo'];
const TARGETS=['academy','dailyCard','music','body','mind','lifeResult','service','membership'];
const mediaRE=/^\/api\/media\/[a-f0-9-]{36}$/,json=JSON.stringify;
function https(v:any){try{const u=new URL(v);return u.protocol==='https:'&&!!u.hostname&&!u.username&&!u.password;}catch{return false;}}
export async function initVideo(_a:any){/* Existing contents/revisions/audits are authoritative. */}
export function validateVTT(value:any,fail:(n:number,s:string)=>never){
 if(typeof value!=='string'||value.length>20000)fail(400,'每个字幕文本最多20000字符。');
 const text=value.replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n').trim();
 if(!/^WEBVTT(?:[ \t][^\n]*)?\n/.test(text+'\n'))fail(400,'字幕须为WEBVTT格式，不能只修改文件扩展名。');
 const cues=[...text.matchAll(/^(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})[ \t]+-->[ \t]+(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})(?:[^\n]*)\n([^\n]+)/gm)];
 if(!cues.length||cues.length!==text.split('\n').filter(line=>line.includes('-->')).length)fail(400,'字幕需要有效时间轴与文字，每条时间格式均须正确。');
 for(const c of cues){const [h1,m1,s1,f1,h2,m2,s2,f2]=c.slice(1,9).map(v=>Number(v||0));if([m1,s1,m2,s2].some(v=>v>59)||((h2*3600+m2*60+s2)*1000+f2)<=((h1*3600+m1*60+s1)*1000+f1))fail(400,'字幕时间范围不正确，结束必须晚于开始。');}
 return text+'\n';
}
export function validateVideoItem(item:any,status:string,fail:(n:number,s:string)=>never){
 if(!item||typeof item!=='object'||Array.isArray(item))fail(400,'轮播内容须为对象。');if(item.mediaType!=='video'){if(![undefined,null,'','image'].includes(item.mediaType)||['mediaUrl','subtitleTracks','mediaReviewed','rightsNote'].some(k=>!!item[k]&&(Array.isArray(item[k])?item[k].length>0:true)))fail(400,'带视频地址或字幕的轮播必须明确声明mediaType为video，不能通过改类型绕过发布校验。');return item;}
 if(!['draft','published','archived'].includes(status))fail(400,'无效发布状态。');
 const allowed=[...TEXT_FIELDS,'id','mediaType','mediaUrl','coverUrl','subtitleTracks','target','rightsNote','mediaReviewed','enabled'];
 if(Object.keys(item).some(k=>!allowed.includes(k)))fail(400,'视频轮播包含未知字段。');
 if(typeof item.id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(item.id))fail(400,'内容编号须为字母、数字、下划线或连字符。');
 const clean:any={id:item.id,mediaType:'video'};
 for(const field of TEXT_FIELDS){const v=item[field]??'',max=field.startsWith('description')?1000:200;if(typeof v!=='string'||v.trim().length>max)fail(400,'轮播多语文字为空或超出长度。');clean[field]=v.trim();}
 for(const field of ['mediaUrl','coverUrl']){const v=item[field]??'';if(typeof v!=='string'||v.length>1500||v&&!mediaRE.test(v)&&!https(v))fail(400,'视频和封面须为本站上传素材或无账号凭据的HTTPS地址。');clean[field]=v;}
 const target=item.target??'';if(typeof target!=='string'||target.length>1500||target&&!TARGETS.includes(target)&&!https(target))fail(400,'跳转须为允许的APP页面或HTTPS地址。');clean.target=target;
 const tracks=item.subtitleTracks??[];if(!Array.isArray(tracks)||tracks.length>4)fail(400,'字幕最多配置简繁英藏四条。');
 const seen=new Set(),result:any[]=[];
 for(const track of tracks){
  if(!track||typeof track!=='object'||Array.isArray(track)||Object.keys(track).some(k=>!['lang','label','url','text'].includes(k))||!LANGUAGES.includes(track.lang)||seen.has(track.lang))fail(400,'字幕语言不正确或重复。');
  const url=track.url||'',text=track.text||'',label=track.label||'';
  if(typeof label!=='string'||label.length>80||!!url===!!text)fail(400,'每条字幕须选择HTTPS地址或WEBVTT文本其中一种。');
  if(url&&(typeof url!=='string'||url.length>1500||!https(url)))fail(400,'外部字幕须为HTTPS地址，并需在目标端验证CORS。');
  result.push({lang:track.lang,label,...(url?{url}:{text:validateVTT(text,fail)})});seen.add(track.lang);
 }
 clean.subtitleTracks=result;
 if(typeof (item.enabled??true)!=='boolean'||typeof (item.mediaReviewed??false)!=='boolean')fail(400,'启用和已审核标记须为布尔值。');clean.enabled=item.enabled??true;clean.mediaReviewed=item.mediaReviewed??false;
 const rights=item.rightsNote||'';if(typeof rights!=='string'||rights.trim().length>2000)fail(400,'素材授权依据最多2000字符。');clean.rightsNote=rights.trim();
 if(status==='published'&&(!clean.zh||!clean.mediaUrl||!clean.coverUrl||!clean.mediaReviewed||!clean.rightsNote||['zh','zh-Hant','en'].some(lang=>!seen.has(lang))))fail(400,'正式发布需要真实视频、封面、简繁英字幕、已审标记与可核对的素材授权依据；资料未齐请存草稿。');
 if(json(clean).length>90000)fail(400,'视频配置过长，请精简字幕。');return clean;
}
export async function authorizeVideoMedia(a:any,item:any,fail:(n:number,s:string)=>never){
 const fields=item.mediaType==='video'?[['mediaUrl','video/'],['coverUrl','image/']]:[['coverUrl','image/']];
 for(const [field,mime] of fields){
  const ref=item[field]||'';if(!mediaRE.test(ref))continue;const r=await a.one('SELECT owner,mime FROM media WHERE id=?',ref.split('/').pop());
  if(!r||!r.mime.startsWith(mime))fail(400,'已上传素材不存在或类型与视频/封面用途不符。');
  const visible=await a.one("SELECT 1 FROM contents WHERE status='published' AND json_extract(data,'$.creatorId') IS NULL AND (kind!='courses' OR COALESCE(json_extract(data,'$.access'),'public')!='member') AND (json_extract(data,'$.mediaUrl')=? OR json_extract(data,'$.coverUrl')=?) LIMIT 1",ref,ref);
  if(r.owner!==a.user.id&&!visible)fail(403,'不能把其他账号的私有素材发布为首页视频或封面。');
 }
}
const rowItem=(r:any)=>({...JSON.parse(r.data),_status:r.status,_position:r.position,_updatedAt:r.updated});
export async function videoRoute(a:any,path:string,method:string,fail:(n:number,s:string)=>never){
 if(path!=='/api/admin/videos')return undefined;a.require(['admin','operator','reviewer']);
 if(method==='GET'){const rows=await a.all("SELECT * FROM contents WHERE kind='quotes' AND json_extract(data,'$.mediaType')='video' ORDER BY position,updated,id");return {items:rows.map(rowItem),formalMediaPresent:rows.some((r:any)=>r.status==='published')};}
 if(!['POST','PATCH'].includes(method))fail(405,'不支持的操作。');a.require(['admin','operator']);await a.rate('home-video-save:'+a.user.id,30);
 const d=await a.body();if(Object.keys(d).some(k=>!['item','status','position','expectedUpdatedAt'].includes(k)))fail(400,'视频管理请求包含未知字段。');
 const status=d.status||'draft',item=validateVideoItem(d.item||{},status,fail);if(item.mediaType!=='video')fail(400,'此入口仅管理视频；原图文轮播在原模块维护。');
 const position=d.position??0;if(!Number.isInteger(position)||position < -10000||position>10000)fail(400,'排序须为-10000至10000整数。');
 const old=await a.one("SELECT * FROM contents WHERE kind='quotes' AND id=?",item.id),expected=old?.updated||0;
 if(!Number.isInteger(d.expectedUpdatedAt)||d.expectedUpdatedAt!==expected)fail(409,'轮播已由其他操作更新，请重新读取后保存。');
 await authorizeVideoMedia(a,item,fail);
 const t=Math.max(Date.now(),expected+1),condition=old?"EXISTS(SELECT 1 FROM contents WHERE kind='quotes' AND id=? AND updated=?)":"NOT EXISTS(SELECT 1 FROM contents WHERE kind='quotes' AND id=?)",args=old?[item.id,expected]:[item.id],statements=[];
 if(old)statements.push(a.stmt('INSERT INTO revisions SELECT ?,?,?,?,?,? WHERE '+condition,crypto.randomUUID(),a.user.id,'quotes',item.id,json(old),t,...args));
 statements.push(a.stmt("INSERT INTO contents SELECT 'quotes',?,?,?,?,? WHERE "+condition+" ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,status=excluded.status,position=excluded.position,updated=excluded.updated",item.id,json(item),status,position,t,...args));
 const results=await a.db.batch(statements);if(!results.at(-1)?.meta?.changes)fail(409,'轮播已由其他操作更新，请重新读取后保存。');
 await a.audit('video.'+status,item.id,'视频配置已保存；素材实际可播放性须目标端验收。');return {item:rowItem(await a.one("SELECT * FROM contents WHERE kind='quotes' AND id=?",item.id))};
}
