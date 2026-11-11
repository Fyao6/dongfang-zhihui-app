import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {writeFile} from 'node:fs/promises';
const qa=path.dirname(fileURLToPath(import.meta.url));
const {default:gateway}=await import(pathToFileURL(path.join(qa,'../04_研发源码/app/cloud/worker/netlify-api.js')));
const oldFetch=globalThis.fetch, results=[];let calls=[];
try {
 globalThis.fetch=async(url,opts)=>{calls.push({url:String(url),opts});const h=new Headers({'content-type':'application/json'});h.append('set-cookie','ew_session=example; Path=/; HttpOnly; Secure; SameSite=Strict');h.append('set-cookie','ew_visitor=example; Path=/; HttpOnly; Secure; SameSite=Strict');h.append('set-cookie','unrelated=must-not-forward');return new Response('{"ok":true}',{headers:h})};
 const base='https://example.netlify.app';
 let r=await gateway(new Request(base+'/api/auth/login',{method:'POST',headers:{origin:'https://attacker.example','content-type':'application/json'},body:'{}'}));assert.equal(r.status,403);assert.equal(calls.length,0);results.push('跨域来源在发往后端前拒绝');
 r=await gateway(new Request(base+'/api/auth/login',{method:'POST',headers:{'sec-fetch-site':'cross-site'},body:'{}'}));assert.equal(r.status,403);assert.equal(calls.length,0);results.push('跨站写请求拒绝');
 r=await gateway(new Request(base+'/api/auth/login',{method:'POST',headers:{origin:base,cookie:'netlify_auth=private; ew_session=demo; ew_visitor=visitor','x-forwarded-host':'attacker','content-type':'application/json'},body:'{"username":"demo"}'}));assert.equal(r.status,200);const call=calls.at(-1);assert.equal(call.opts.headers.get('origin'),'https://eastern-wisdom-demo-20261102.sturdyebony2.chatgpt.site');assert.equal(call.opts.headers.get('cookie'),'ew_session=demo; ew_visitor=visitor');assert.equal(call.opts.headers.has('x-forwarded-host'),false);assert.equal(await new Response(call.opts.body).text(),'{"username":"demo"}');assert.equal(r.headers.getSetCookie().length,2);assert.equal(r.headers.get('cache-control'),'no-store');results.push('同源登录请求体和双Cookie正确转发，平台Cookie不外传');
 globalThis.fetch=async(url,opts)=>{assert.equal(opts.headers.get('range'),'bytes=1-3');return new Response(new Uint8Array([1,2,3]),{status:206,headers:{'content-type':'video/mp4','content-range':'bytes 1-3/10','accept-ranges':'bytes'}})};
 r=await gateway(new Request(base+'/api/media/test',{headers:{range:'bytes=1-3'}}));assert.equal(r.status,206);assert.equal(r.headers.get('content-range'),'bytes 1-3/10');assert.equal((await r.arrayBuffer()).byteLength,3);results.push('媒体Range状态与二进制保持');
 globalThis.fetch=async()=>{throw Error('private diagnostic must not leak')};r=await gateway(new Request(base+'/api/health'));assert.equal(r.status,502);assert(!(await r.text()).includes('diagnostic'));results.push('连接失败返回可读错误而不泄露内部信息');
 r=await gateway(new Request(base+'/admin'));assert.equal(r.status,404);results.push('仅代理API路径');
 await writeFile(path.join(qa,'Netlify网关回归结果.json'),JSON.stringify({at:new Date().toISOString(),pass:true,checks:results},null,2));console.log(JSON.stringify({pass:true,checks:results}));
}finally{globalThis.fetch=oldFetch}
