// Same-origin entry to the existing, user-owned cloud backend.
// No privileged credentials are embedded here. Every request keeps its existing role checks.
const BACKEND = 'https://eastern-wisdom-demo-20261102.sturdyebony2.chatgpt.site';
const mutation = new Set(['POST','PATCH','PUT','DELETE']);
function error(message,status) {return Response.json({error:message},{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})}
export default async function gateway(request) {
  const url=new URL(request.url);
  if(!url.pathname.startsWith('/api/')) return error('未找到此接口。',404);
  const origin=request.headers.get('origin');
  if(origin && origin!==url.origin) return error('不允许跨站请求。',403);
  if(mutation.has(request.method) && request.headers.get('sec-fetch-site')==='cross-site') return error('不允许跨站请求。',403);
  if(!['GET','HEAD','POST','PATCH','PUT','DELETE'].includes(request.method)) return error('不支持的请求方式。',405);
  const headers=new Headers();
  for(const key of ['content-type','content-length','range','if-range','accept','authorization','x-filename']) {
    const value=request.headers.get(key); if(value!==null) headers.set(key,value);
  }
  const cookie=(request.headers.get('cookie')||'').split(';').map(x=>x.trim()).filter(x=>/^ew_(session|visitor)=/.test(x)).join('; ');
  if(cookie) headers.set('cookie',cookie);
  // Origin is rewritten only after validating the browser's original origin above.
  if(origin) headers.set('origin',BACKEND);
  try {
    const upstream=await fetch(new URL(url.pathname+url.search,BACKEND),{
      method:request.method,headers,body:['GET','HEAD'].includes(request.method)?undefined:request.body,
      duplex:'half',redirect:'error',signal:AbortSignal.timeout(65000)
    });
    const responseHeaders=new Headers({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','X-Robots-Tag':'noindex, nofollow'});
    for(const key of ['content-type','content-range','accept-ranges','etag','retry-after']) {
      const value=upstream.headers.get(key); if(value!==null) responseHeaders.set(key,value);
    }
    // The backend issues host-only cookies. They become cookies of this Netlify site.
    for(const cookie of upstream.headers.getSetCookie()) if(/^ew_(session|visitor)=/.test(cookie)) responseHeaders.append('set-cookie',cookie);
    return new Response(upstream.body,{status:upstream.status,headers:responseHeaders});
  } catch {return error('云端服务暂时连接失败，请稍后重试。',502)}
}
