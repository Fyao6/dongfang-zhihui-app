// Fixed owned sandbox business-time seam. No authentication/session/limiter/DB clock changes.
import nativeService from './负责人优化建议-卡组迁移Cloud测试服务';
import {MembershipLifecycle} from '../04_研发源码/app/cloud/lib/membership-lifecycle';
const nativeClock=MembershipLifecycle.prototype.clock,realNow=Date.now.bind(Date);
let base:number|null=null,started=realNow();
MembershipLifecycle.prototype.clock=function(){return base===null?nativeClock.call(this):base+Math.max(0,realNow()-started);};
export default {async fetch(request:Request,env:any,ctx:any){
 const url=new URL(request.url);
 if(url.pathname==='/__card-migration-test/control'&&request.method==='POST'&&url.hostname==='127.0.0.1'&&request.headers.get('X-Card-Migration-Test')===env.CARD_MIGRATION_TEST_TOKEN){
  const raw=await request.clone().text();if(raw.length<=4096){const d=JSON.parse(raw);if(d.action==='membership-clock'){
   if(d.nowMs!==null&&(!Number.isSafeInteger(d.nowMs)||d.nowMs<=0||d.nowMs>=4000000000000))return Response.json({error:'Invalid owned clock'},{status:400});
   base=d.nowMs;started=realNow();return Response.json({isolated:true,clockFixture:'sandbox_synthetic_business_time',nowMs:base,authenticationClockChanged:false});
  }}
 }
 return nativeService.fetch(request,env,ctx);
}};
