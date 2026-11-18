'use strict';
// Real paused TCP receiver for the owned loopback media server. Headers/cookies never leave this function.
const net=require('node:net'),crypto=require('node:crypto'),assert=require('node:assert/strict');
function largeWav(){const bytes=Buffer.alloc(24*1024*1024);bytes.write('RIFF',0);bytes.writeUInt32LE(bytes.length-8,4);bytes.write('WAVEfmt ',8);bytes.writeUInt32LE(16,16);bytes.writeUInt16LE(1,20);bytes.writeUInt16LE(1,22);bytes.writeUInt32LE(8000,24);bytes.writeUInt32LE(16000,28);bytes.writeUInt16LE(2,32);bytes.writeUInt16LE(16,34);bytes.write('data',36);bytes.writeUInt32LE(bytes.length-44,40);return bytes;}
async function pausedMedia(h,context,url){
 const u=new URL(url,h.base);assert.equal(u.origin,h.base);assert.equal(u.hostname,'127.0.0.1');const storage=await context.storageState(),cookies=storage.cookies.filter(x=>['127.0.0.1','localhost'].includes(x.domain)).map(x=>x.name+'='+x.value).join('; ');
 let headerBytes=Buffer.alloc(0),headersSeen=false,bodyBytes=0,status=0,length=0,done=false,resolveHeaders,rejectHeaders,resolveDone,rejectDone;const hash=crypto.createHash('sha256');
 const head=new Promise((resolve,reject)=>{resolveHeaders=resolve;rejectHeaders=reject;}),completion=new Promise((resolve,reject)=>{resolveDone=resolve;rejectDone=reject;});completion.catch(()=>{});
 const socket=net.createConnection({host:'127.0.0.1',port:Number(u.port)});socket.setTimeout(45000,()=>socket.destroy(Error('Owned slow receiver timed out')));
 socket.on('connect',()=>socket.write('GET '+u.pathname+u.search+' HTTP/1.1\r\nHost: '+u.host+'\r\nCookie: '+cookies+'\r\nConnection: close\r\n\r\n'));
 socket.on('data',chunk=>{if(!headersSeen){headerBytes=Buffer.concat([headerBytes,chunk]);const stop=headerBytes.indexOf('\r\n\r\n');if(stop<0)return;const text=headerBytes.subarray(0,stop).toString('latin1');status=Number(/^HTTP\/1\.\d\s+(\d+)/.exec(text)?.[1]);length=Number(/\r\nContent-Length:\s*(\d+)/i.exec(text)?.[1]);const body=headerBytes.subarray(stop+4);bodyBytes+=body.length;hash.update(body);headersSeen=true;headerBytes=Buffer.alloc(0);socket.pause();resolveHeaders({status,contentLength:length,pausedAfterHeaders:true});return;}bodyBytes+=chunk.length;hash.update(chunk);});
 socket.on('end',()=>{done=true;resolveDone({status,bytes:bodyBytes,contentLength:length,sha256:hash.digest('hex')});});socket.on('error',error=>{rejectHeaders(error);rejectDone(error);});
 const metadata=await head;return {...metadata,resume:()=>socket.resume(),close:()=>socket.destroy(),finished:()=>done,completion};
}
module.exports={largeWav,pausedMedia};
