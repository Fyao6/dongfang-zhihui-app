'use strict';
// Fixed, one-request worker. No DOM, shell, network or client-selected module path.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const R4=path.resolve(__dirname,'..'),PROJECT=path.resolve(R4,'../../..');
const INPUT_LIMIT=6*1024*1024,OUTPUT_LIMIT=4*1024*1024;
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
let answered=false;
function reply(value){if(answered)return;let encoded;try{encoded=JSON.stringify(value);}catch{encoded=JSON.stringify({ok:false,error:{code:'worker_failed',path:'',status:500}});}if(Buffer.byteLength(encoded,'utf8')+1>OUTPUT_LIMIT)encoded=JSON.stringify({ok:false,error:{code:'output_too_large',path:'',status:413}});answered=true;process.stdout.write(encoded+'\n');}
function failed(error){reply({ok:false,error:{code:/^[A-Za-z_][A-Za-z0-9_-]{0,99}$/.test(error?.code||'')?error.code:'worker_failed',path:typeof error?.path==='string'?error.path.slice(0,1000):'',status:[400,404,409,413,500,503].includes(error?.status)?error.status:500}});}
const MANAGED=[
 '04_研发源码/app/r4/bazi-sample-engine.js','04_研发源码/app/r4/bazi-sample-engine.d.ts','04_研发源码/app/r4/bazi-sample-bridge.js','04_研发源码/app/r4/bazi-samples-ui.js',
 '04_研发源码/app/r4/life-chart-core.js','04_研发源码/app/r4/life-chart-bazi.js','04_研发源码/app/r4/bazi-time.js','04_研发源码/app/r4/bazi-compare.js','04_研发源码/app/r4/life-chart-bazi-annotations.js','04_研发源码/app/r4/life-chart-bazi-layout.js','04_研发源码/app/r4/life-birth-entry.js',
 '04_研发源码/app/r4/bazi-result-version.js','04_研发源码/app/r4/bazi-result-version-ui.js','04_研发源码/app/r4/bazi-result-version-release.js','04_研发源码/app/r4/bazi-interpretation-bridge.js','04_研发源码/app/r4/backend/bazi_sample_worker.cjs',
 '04_研发源码/app/r4/vendor/lunar-1.7.7.js','04_研发源码/app/r4/vendor/lunar-1.7.7-LICENSE.txt','04_研发源码/app/r4/build_bazi_sample_manifest.py','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py'
];
async function identity(engine){
 const sourceHashes={},missingSources=[];for(const relative of MANAGED){const file=path.join(PROJECT,relative);try{sourceHashes[relative]=hash(fs.readFileSync(file));}catch{missingSources.push(relative);}}
 let manifest=null,valid=false;try{manifest=engine.strictParse(fs.readFileSync(path.join(R4,'bazi-sample-source-manifest.json'),'utf8'),2097152);const core={...manifest};delete core.manifestSha256;valid=manifest.schema===1&&manifest.kind==='bazi-sample-managed-source'&&manifest.implementationReady===true&&manifest.teacherConfirmed===false&&manifest.professionalValidation===false&&hash(engine.canonical(core))===manifest.manifestSha256&&missingSources.length===0&&engine.canonical(manifest.sourceHashes)===engine.canonical(sourceHashes)&&Array.isArray(manifest.missingSources)&&manifest.missingSources.length===0;}catch{valid=false;}
 const vendor=sourceHashes['04_研发源码/app/r4/vendor/lunar-1.7.7.js'];valid=valid&&vendor==='9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa'&&sourceHashes['04_研发源码/app/r4/vendor/lunar-1.7.7-LICENSE.txt']==='d9210caf1844dcf410095cea464b79800aad30dbd49df092076b9f0ddc015404';
 return {engine:{name:'lunar-javascript',version:'1.7.7',vendorSha256:vendor||null},adapterVersion:engine.adapterVersion,ruleVersion:engine.ruleVersion,annotationRulesVersion:'eastern-bazi-annotations-2',manifest,sourceHashes,missingSources,runtime:{node:process.versions.node||null,icu:process.versions.icu||null,tz:process.versions.tz||null,unicode:process.versions.unicode||null},implementationReady:valid,teacherConfirmed:false,professionalValidation:false};
}
async function main(buffer){
 const factory=require(path.join(R4,'bazi-sample-engine.js')),lunar=require(path.join(R4,'vendor/lunar-1.7.7.js')),engine=factory.createEngine({lunar,sha256:text=>hash(Buffer.from(text,'utf8'))});
 let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(buffer);}catch{throw Object.assign(new Error(),{code:'invalid_utf8',status:400});}
 const request=engine.strictParse(text,INPUT_LIMIT);if(!request||Array.isArray(request)||typeof request!=='object')throw Object.assign(new Error(),{code:'invalid_worker_request',status:400});
 const keys={identity:['op'],validate:['op','rawText'],compute:['op','case']}[request.op];if(!keys||Object.keys(request).length!==keys.length||Object.keys(request).some(k=>!keys.includes(k)))throw Object.assign(new Error(),{code:'invalid_worker_request',status:400});
 if(request.op==='identity')return identity(engine);
 if(request.op==='validate')return engine.validateDataset(request.rawText);
 return engine.computeCase(request.case);
}
let size=0,chunks=[];process.stdin.on('data',chunk=>{if(answered)return;size+=chunk.length;if(size>INPUT_LIMIT){failed({code:'worker_input_too_large',status:413});chunks=[];process.stdin.destroy();return;}chunks.push(chunk);});
process.stdin.on('end',()=>{if(!answered)main(Buffer.concat(chunks)).then(result=>reply({ok:true,result}),failed);});
process.stdin.on('error',()=>{if(!answered)failed({code:'worker_input_failed',status:500});});
process.on('uncaughtException',()=>failed({code:'worker_failed',status:500}));
process.on('unhandledRejection',()=>failed({code:'worker_failed',status:500}));
