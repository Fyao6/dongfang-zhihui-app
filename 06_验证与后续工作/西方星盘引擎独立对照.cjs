// Independent official Swiss test output is reference data only, not an app dependency.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4');
const A=require(path.join(r4,'vendor/astronomy-engine-2.1.19.min.js'));
const context={LCAstronomy:A,Date,Math,JSON,Number,String,Object,Array,lcText:(en)=>en,screens:{},document:{addEventListener(){}},console};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(r4,'life-chart-western.js'),'utf8'),context);
const references=JSON.parse(fs.readFileSync(path.join(__dirname,'西方星盘官方独立样例.json'),'utf8')),results=[];
const difference=(a,b)=>Math.abs(((a-b+540)%360)-180);
let maxPlanetError=0,maxAngleError=0,maxSpeedError=0;
for(const test of references.cases){
 const input={utc:test.utc,birth:{date:test.utc.slice(0,10),time:test.utc.slice(11,16),timezone:'UTC',latitude:test.latitude,longitude:test.longitude,place:'Public validation fixture'}};
 const actual=context.lcWesternCalculate(input,{houseSystem:'equal'});
 for(const p of actual.planets){const expected=test.planets[p.id],lonError=difference(p.longitude,expected.longitude),latError=Math.abs(p.latitude-expected.latitude),speedError=Math.abs(p.speed-expected.speed);maxPlanetError=Math.max(maxPlanetError,lonError,latError);maxSpeedError=Math.max(maxSpeedError,speedError);assert(lonError<=0.03,test.id+' '+p.id+' independent longitude '+lonError);assert(latError<=0.03,test.id+' '+p.id+' independent latitude '+latError);assert(speedError<=0.03,test.id+' '+p.id+' daily speed '+speedError);assert.equal(p.retrograde,expected.speed<0,test.id+' '+p.id+' retrograde sign');}
 for(const key of ['ascendant','mc']){const error=difference(actual.angles[key],test.angles[key]);maxAngleError=Math.max(maxAngleError,error);assert(error<=0.01,test.id+' independent '+key+' '+error);}
 for(const h of actual.houses)assert(difference(h.start,test.houses.find(x=>x.number===h.number).start)<=0.01,test.id+' equal house '+h.number);
 assert.equal(actual.planets.length,10);assert.equal(actual.houses.length,12);assert(actual.aspects.every(a=>a.orb<=a.limit&&a.limit===actual.rules.aspectOrbs[a.type]));
 assert(JSON.stringify(actual).length>1000,'Result is full serializable chart data');assert.equal(JSON.parse(JSON.stringify(actual)).engine.version,'2.1.19');
 const whole=context.lcWesternCalculate(input,{houseSystem:'whole-sign'});assert(whole.houses.every(h=>Math.abs(h.start%30)<1e-9));assert.equal(whole.angles.ascendant,actual.angles.ascendant);assert(whole.planets.every((p,i)=>p.longitude===actual.planets[i].longitude),'House system cannot alter astronomical positions');
 results.push({name:test.id,pass:true,source:test.source_url});
}
const common={utc:'2000-01-01T12:00:00Z',birth:{date:'2000-01-01',time:'12:00',timezone:'UTC',latitude:51.4779,longitude:0}};
for(const [name,input,options] of [
 ['missing time',{...common,birth:{...common.birth,time:''}},{}],
 ['invalid birth clock',{...common,birth:{...common.birth,time:'unknown'}},{}],
 ['empty coordinates',{...common,birth:{...common.birth,latitude:'',longitude:''}},{}],
 ['unknown time',{...common,birth:{...common.birth,timeUnknown:true}},{}],
 ['invalid time',{...common,utc:'not-a-date'},{}],
 ['out-of-range date',{...common,utc:'1500-01-01T12:00:00Z'},{}],
 ['north pole',{...common,birth:{...common.birth,latitude:90}},{}],
 ['south pole',{...common,birth:{...common.birth,latitude:-90}},{}],
 ['bad longitude',{...common,birth:{...common.birth,longitude:181}},{}],
 ['missing coordinates',{...common,birth:{time:'12:00'}},{}],
 ['unsupported houses',common,{houseSystem:'placidus'}]
]){assert.throws(()=>context.lcWesternCalculate(input,options),name+' must not generate a fabricated/NaN chart');results.push({name,pass:true});}
const chart=context.lcWesternCalculate(common,{houseSystem:'whole-sign'}),shift=context.lcWesternCalculate({...common,birth:{...common.birth,longitude:116.4}},{houseSystem:'whole-sign'});
assert(chart.planets.every((p,i)=>p.longitude===shift.planets[i].longitude),'Geocentric positions are independent of birthplace longitude');assert(difference(chart.angles.ascendant,shift.angles.ascendant)>1,'ASC must depend on actual birthplace longitude');
results.push({name:'Birthplace changes angles, not geocentric planetary positions',pass:true});
const report={at:new Date().toISOString(),pass:true,passed:results.length,failed:0,engine:'Astronomy Engine 2.1.19 (MIT)',independentSource:'Astrodienst official Swiss Ephemeris swetest CGI, public synthetic fixtures; no Swiss runtime bundled',comparisonCases:references.cases.length,independentPlanetComparisons:references.cases.length*10,independentAngleComparisons:references.cases.length*2,maxPlanetErrorDegrees:maxPlanetError,maxAngleErrorDegrees:maxAngleError,maxSpeedErrorDegreesPerDay:maxSpeedError,limits:'Five selected independent instants and locations do not establish accuracy for every date. Supported UI model is tropical apparent geocentric, whole-sign/equal houses only. No predictive interpretation validation is claimed.',sourceSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(r4,'life-chart-western.js'))).digest('hex'),results};
const file=path.join(__dirname,'西方星盘引擎独立对照结果.json');let runs=[];if(fs.existsSync(file))try{const old=JSON.parse(fs.readFileSync(file));runs=old.runs||[old];}catch{}runs.push(report);fs.writeFileSync(file,JSON.stringify({latest:report,runs},null,2));console.log(JSON.stringify({pass:report.pass,passed:report.passed,maxPlanetErrorDegrees:maxPlanetError,maxAngleErrorDegrees:maxAngleError},null,2));
