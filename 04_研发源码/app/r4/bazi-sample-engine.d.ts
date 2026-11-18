export type Json = null | boolean | number | string | Json[] | {[key:string]:Json};
export interface SampleCase {
 caseId:string; label:string; tags:string[];
 input:{date:string;time:string|null;sex:'male'|'female';name?:string};
 context:{mode:'shared-current'|'legacy-reference'|'isolated-fixture';legacyTimezone:string|null;archivedUtc:string|null;sourceRecordSha256:string|null;ambiguity:'reject'|'earlier'|'later';asOfUtc:string};
 options:{daySect:1|2;yunSect:1|2;trueSolarTime:false};
 selection:{mode:'current'|'manual';period:number|null;year:number|null;month:number|null};
 expected:Record<string,{state:'value';value:Json}|{state:'not_applicable';reasonCode:string}>;
 expectedRuleIdentity:null|{engine:null|{name:string;version:string};ruleVersion:string|null;annotationRulesVersion:string|null;options:SampleCase['options']|null};
 teacherApproval:{claimedReviewer:string|null;evidenceReference:string|null;evidenceSha256:string|null;verification:'unverified-external-claim'};
}
export interface Dataset {schema:1;setId:string;version:string;title:string;source:{kind:'synthetic'|'teacher-provided'|'legacy-reference';reference:string;documentSha256:string|null;permissionReference:string|null};cases:SampleCase[]}
export interface FieldResult {caseId:string;stage:string;path:string;column:string|null;expectedState:string;expected:Json;actualState:string;actual:Json;comparison:string;reasonCode:string;category:'undetermined';classificationState:'unclassified';evidence:{stageFingerprint:string|null}}
export interface ComputedCase {caseId:string;status:'succeeded'|'blocked'|'failed';errorCode:string;stages:Record<string,any>;timing:any;selection:any;expectations:SampleCase['expected'];fieldResults:FieldResult[];fieldIndex:{path:string;stage:string;column:string|null;actualState:string}[];counts:Record<string,number|null>;fingerprints:Record<string,string>;rawIndex:{sha256:string|null;byteLength:number;periodCount:number;yearCount:number;monthCount:number;smallFortuneCount:number};teacherConfirmed:false;professionalValidation:false;domStatus:'not_run';ruleIdentity:any}
export interface Engine {
 canonical(value:any):string;strictParse(text:string,maxBytes?:number):any;validateCase(value:any,path?:string):SampleCase;
 validateDataset(rawText:string):Promise<{dataset:Dataset;sourceBytesSha256:string;sourceByteLength:number;canonicalSha256:string;canonicalByteLength:number;cases:{caseId:string;ordinal:number;canonicalSha256:string;canonicalByteLength:number}[];teacherConfirmed:false;professionalValidation:false}>;
 computeCase(value:SampleCase):Promise<ComputedCase>;
 listFields(report:ComputedCase,options?:{before?:string|null;limit?:number}):{items:FieldResult[];next:string|null;counts:ComputedCase['counts']};
 splitRaw(raw:any):Promise<{header:any;headerSha256:string|null;headerByteLength:number;periods:{index:number;data:any;sha256:string;byteLength:number}[];sha256:string|null;byteLength:number}>;
 pathAllowed(path:string):boolean;actualAt(report:ComputedCase,path:string):any;
 normalizeInput(raw:any,options?:any):any;parts(ms:number,zone:string):any;chinaParts(iso:string):any;calculate(normalized:any,options?:any):any;
 resolveSelection(raw:any,state:any,asOfMs?:number):any;currentSelection(raw:any,asOfMs?:number):any;calendarAt(asOfMs?:number):any;monthInterval(year:number,index:number):any;timeTerms(year:number):any;timeCivilMs(value:any):number;timeMoment(value:any):number;
 buildComparison(raw:any,selection?:any):any;describePillar(ganZhi:string,dayMaster:string,context?:any):any;comparisonPick(items:any[],index:number|undefined,label:string):any;buildAnnotations(raw:any,comparison:any):any;annotationPillar(p:any,u:any,allowEmpty?:boolean):any;annotationSelfStage(stem:string,branch:string,u:any):string;
 readonly limits:Record<string,number>;readonly tags:readonly string[];readonly notApplicableReasons:readonly string[];readonly engine:{name:string;version:string};readonly ruleVersion:string;readonly adapterVersion:string;
}
export function createEngine(options:{lunar:any;sha256?:(utf8Text:string)=>Promise<string>|string}):Engine;
declare const api:{createEngine:typeof createEngine;LIMITS:Readonly<Record<string,number>>;TAGS:readonly string[];ENGINE:{name:string;version:string};RULE_VERSION:string;ADAPTER_VERSION:string};
export default api;
