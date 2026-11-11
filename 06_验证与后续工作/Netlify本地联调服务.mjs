import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {Readable} from 'node:stream';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const project=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const cloud=path.join(project,'04_研发源码/app/cloud');
const {default:gateway}=await import(pathToFileURL(path.join(cloud,'worker/netlify-api.js')));
const nativeFetch=globalThis.fetch;
// Isolated integration transport: replace the deployed backend with the identical local Worker.
globalThis.fetch=(url,init={})=>{
 const u=new URL(url);if(u.origin==='https://eastern-wisdom-demo-20261102.sturdyebony2.chatgpt.site'){
  u.protocol='http:';u.host='127.0.0.1:8877';
  const h=new Headers(init.headers);if(h.has('origin'))h.set('origin',u.origin);
  return nativeFetch(u,{...init,headers:h});
 }
 return nativeFetch(url,init);
};
const root=path.join(cloud,'.netlify/public');
const mime={'.html':'text/html; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.mp4':'video/mp4','.txt':'text/plain','.woff2':'font/woff2'};
const server=http.createServer(async(req,res)=>{
 try{
 const u=new URL(req.url,'http://127.0.0.1:8878');
 if(u.pathname.startsWith('/api/')){
  const request=new Request(u,{method:req.method,headers:req.headers,body:['GET','HEAD'].includes(req.method)?undefined:Readable.toWeb(req),duplex:'half'});
  const response=await gateway(request);res.statusCode=response.status;
  for(const [k,v] of response.headers)if(k!=='set-cookie')res.setHeader(k,v);
  const cookies=response.headers.getSetCookie();if(cookies.length)res.setHeader('set-cookie',cookies);
  if(response.body)Readable.fromWeb(response.body).pipe(res);else res.end();return;
 }
 const mapping={'/':'index.html','/experience':'experience.html','/app':'app.html','/admin':'admin.html'};
 const f=path.resolve(root,mapping[u.pathname]||'.'+decodeURIComponent(u.pathname));
 if(!f.startsWith(root+path.sep)){res.writeHead(403).end();return}
 let buf;try{buf=await readFile(f)}catch{res.writeHead(404).end();return}
 res.setHeader('content-type',mime[path.extname(f)]||'application/octet-stream');res.setHeader('accept-ranges','bytes');
 const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
 if(range){const start=Number(range[1]),end=range[2]?Math.min(Number(range[2]),buf.length-1):buf.length-1;if(start> end){res.writeHead(416).end();return}res.statusCode=206;res.setHeader('content-range',`bytes ${start}-${end}/${buf.length}`);buf=buf.subarray(start,end+1)}
 res.setHeader('content-length',buf.length);res.end(req.method==='HEAD'?undefined:buf);
 }catch(e){console.error(e.message);res.writeHead(500).end('Local validation server error')}
});server.listen(8878,'127.0.0.1',()=>console.log('Netlify entry validation at http://127.0.0.1:8878; local D1 only.'));
