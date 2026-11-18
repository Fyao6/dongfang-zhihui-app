from pathlib import Path
P=Path(__file__).resolve().parent.parent
def edit(name, pairs):
 p=P/name;s=p.read_text(encoding='utf-8')
 for old,new in pairs:
  if s.count(old)!=1:raise RuntimeError(name+' anchor count '+str(s.count(old))+': '+old[:90])
  s=s.replace(old,new)
 p.write_text(s,encoding='utf-8',newline='\r\n')
edit('04_研发源码/app/r4/build.py',[
 ("'ai-gateway-ui.css']", "'ai-gateway-ui.css','membership-lifecycle-ui.css']"),
 ("'ai-gateway-ui.js','i18n-ui.js']", "'ai-gateway-ui.js','membership-lifecycle-ui.js','i18n-ui.js']"),
 (".replace('/*__AI_GATEWAY_ADMIN__*/',(ROOT/'ai-gateway-admin.js').read_text(encoding='utf-8'))", ".replace('/*__AI_GATEWAY_ADMIN__*/',(ROOT/'ai-gateway-admin.js').read_text(encoding='utf-8')).replace('/*__MEMBERSHIP_ADMIN__*/',(ROOT/'membership-lifecycle-admin.js').read_text(encoding='utf-8'))")
])
edit('04_研发源码/app/cloud/prepare.py',[
 (".replace('/*__AI_GATEWAY_ADMIN__*/',(source/'ai-gateway-admin.js').read_text(encoding='utf-8'))", ".replace('/*__AI_GATEWAY_ADMIN__*/',(source/'ai-gateway-admin.js').read_text(encoding='utf-8')).replace('/*__MEMBERSHIP_ADMIN__*/',(source/'membership-lifecycle-admin.js').read_text(encoding='utf-8'))")
])
edit('04_研发源码/app/r4/time-bank-admin.html',[
 ("'commerce','privacy','aiGateway'", "'commerce','privacy','aiGateway','memberSubscriptions'"),
 ("/*__AI_GATEWAY_ADMIN__*/", "/*__AI_GATEWAY_ADMIN__*/\n/*__MEMBERSHIP_ADMIN__*/")
])
edit('04_研发源码/app/r4/platform.js',[
 ("gatewayReady:!!d.aiGatewayReady,loaded:true", "gatewayReady:!!d.aiGatewayReady,membershipServiceReady:!!d.membershipServiceReady,loaded:true")
])
queries={
 'membershipSubscriptions':'SELECT id,environment,group_id,plan_id,plan_version,status,auto_renew,period_start,period_end,grace_end,trial_end,next_charge_at,cancelled_at,version,created,updated FROM membership_subscriptions WHERE owner=?',
 'membershipOrderTerms':'SELECT item_id,environment,order_id,plan_id,plan_version,group_id,data,subscription_id,payment_event_id,period_start,period_end,state,created FROM membership_order_snapshots WHERE owner=?',
 'membershipEvents':'SELECT id,environment,subscription_id,request_id,kind,data,created FROM membership_events WHERE owner=?',
 'membershipPurchaseLocks':'SELECT environment,group_id,order_id,subscription_id,expires FROM membership_purchase_locks WHERE owner=?'
}
edit('04_研发源码/app/r4/backend/privacy.py',[
 ("            'aiGatewayWallet':",''.join("            "+repr(k)+": ("+repr(v)+",),\n" for k,v in queries.items())+"            'aiGatewayWallet':")
])
edit('04_研发源码/app/cloud/lib/privacy-api.ts',[
 ("   aiGatewayWallet:",''.join('   '+k+':'+repr(v)+',\n' for k,v in queries.items())+"   aiGatewayWallet:")
])
print('membership frontend/build/privacy hooks applied')

