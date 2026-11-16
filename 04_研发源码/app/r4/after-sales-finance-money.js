// Exact decimal input in the original currency's major unit. No floating-point parsing.
(function(root){
 'use strict';
 const codes='CNY USD EUR GBP HKD TWD JPY KRW CAD AUD NZD SGD CHF THB MYR IDR VND PHP INR AED SAR BRL MXN ZAR BHD KWD OMR JOD TND'.split(' ');
 function exponent(currency){if(!codes.includes(currency))throw Error('Unsupported original currency');return ['JPY','KRW','IDR','VND'].includes(currency)?0:['KWD','BHD','OMR','JOD','TND'].includes(currency)?3:2;}
 function parse(value,currency,nullable=false){
  if(typeof value!=='string')throw Error('Amount must be explicit decimal text');
  const raw=value.trim(),d=exponent(currency);if(!raw&&nullable)return null;
  if(!new RegExp('^(0|[1-9][0-9]*)(?:\\.([0-9]{1,'+Math.max(d,1)+'}))?$').test(raw)||(!d&&raw.includes('.')))throw Error('Invalid currency amount');
  const [whole,fraction='']=raw.split('.');if(fraction.length>d)throw Error('Too many decimal places');
  const minor=BigInt(whole)*10n**BigInt(d)+BigInt((fraction+'0'.repeat(d)).slice(0,d)||'0');
  if(minor>1000000000n)throw Error('Amount exceeds supported range');return Number(minor);
 }
 function decimal(minor,currency){const d=exponent(currency);if(!Number.isSafeInteger(minor)||minor<0)throw Error('Invalid minor amount');const raw=String(minor).padStart(d+1,'0');return d?raw.slice(0,-d)+'.'+raw.slice(-d):raw;}
 function format(minor,currency){return minor===null||minor===undefined?'—':currency+' '+decimal(minor,currency);}
 root.AfterSalesFinanceMoney=Object.freeze({exponent,parse,decimal,format,currencies:Object.freeze(codes)});
})(typeof globalThis==='object'?globalThis:this);
