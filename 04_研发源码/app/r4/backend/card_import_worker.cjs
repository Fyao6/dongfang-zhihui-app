'use strict';
// Fixed one-request pure validator. No network, DOM, user module paths or shell.
const engine=require('../card-import-engine.js'),INPUT=6*1024*1024,OUTPUT=8*1024*1024;
let size=0,chunks=[],answered=false;
const dictionaryWire=value=>engine.packWire(value);
function reply(value,compact=false){if(answered)return;if(compact&&value.ok)value={ok:true,...dictionaryWire(value.result)};let out=JSON.stringify(value);if(Buffer.byteLength(out)+1>OUTPUT)out=JSON.stringify({ok:false,error:{code:'output_too_large',path:'',status:413}});answered=true;process.stdout.write(out+'\n');}
function error(e){reply({ok:false,error:{code:/^[a-zA-Z_][a-zA-Z0-9_-]{0,99}$/.test(e?.code||'')?e.code:'worker_failed',path:typeof e?.path==='string'?e.path.slice(0,1000):'',status:[400,413,500].includes(e?.status)?e.status:500}});}
process.stdin.on('data',b=>{if(answered)return;size+=b.length;if(size>INPUT){chunks=[];error({code:'worker_input_too_large',status:413});process.stdin.destroy();return;}chunks.push(b);});
process.stdin.on('end',()=>{if(answered)return;try{const request=engine.parseStrict(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks)));const keys={parse:['op','rawText'],canonical:['op','payload'],inspect:['op','payload','baseData'],identity:['op']}[request.op];if(!keys||Object.keys(request).length!==keys.length||Object.keys(request).some(k=>!keys.includes(k)))throw {code:'invalid_worker_request',status:400};let result;if(request.op==='parse')result=engine.parseStrict(request.rawText);else if(request.op==='canonical')result=engine.canonical(request.payload);else if(request.op==='inspect')result=engine.inspect(request.payload,request.baseData);else result={version:engine.version};reply({ok:true,result},request.op==='inspect');}catch(e){error(e);}});
process.stdin.on('error',()=>error({code:'worker_input_failed',status:500}));process.on('uncaughtException',error);process.on('unhandledRejection',error);
