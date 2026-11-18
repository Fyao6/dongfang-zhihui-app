'use strict';
// Only NEW task-alert diagnostic output is filtered, before its first disk write.
// Frozen scripts/inputs and all assertion values remain unchanged.
const fs=require('node:fs'),path=require('node:path');
const out=__dirname,prefix='负责人优化建议-任务告警',native=fs.writeFileSync;
function clean(value){let result=String(value).replace(/(\bew_session=)[^\s;,"'\\]+/gi,'$1[REDACTED_SESSION]').replace(/(\bBearer\s+)[A-Za-z0-9._~+\/-]+/gi,'$1[REDACTED_TOKEN]');for(const [name,secret]of Object.entries(process.env))if(/SECRET|TOKEN|PASSWORD|CREDENTIAL|SESSION|^EW_AI_/i.test(name)&&secret?.length>=12)result=result.split(secret).join('[REDACTED_QA_SECRET]');try{const password=JSON.parse(process.env.EW_CLOUD_QA_CREDENTIALS||'{}').password;if(password?.length>=8)result=result.split(password).join('[REDACTED_QA_PASSWORD]');}catch{}return result;}
fs.writeFileSync=function(file,data,...options){if(typeof file==='string'&&path.dirname(path.resolve(file))===out&&path.basename(file).startsWith(prefix)&&/\.(json|log|txt)$/i.test(file)&&(typeof data==='string'||Buffer.isBuffer(data)))return native.call(this,file,clean(Buffer.isBuffer(data)?data.toString('utf8'):data),...options);return native.call(this,file,data,...options);};
