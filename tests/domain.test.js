const {test}=require('node:test'),assert=require('node:assert/strict');
const {splitBill,relevantMemory,apps}=require('../electron/renderer/domain');
test('split includes tax and pre-tax tip',()=>{const s=splitBill([68.50],5.31,18,3);assert.equal(s.total,86.14);assert.deepEqual(s.shares,[28.72,28.71,28.71]);});
test('rounding never loses a cent',()=>{for(let n=1;n<40;n++){const s=splitBill([19.99,3.45],2.11,20,n);assert.equal(s.shares.reduce((sum,x)=>sum+Math.round(x*100),0),Math.round(s.total*100));}});
test('rejects invalid amounts and people',()=>{for(const args of [[[-1],0,0,2],[[1],0,-20,2],[[1],0,10,0],[[1],0,10,2.5],[[Infinity],0,10,2]])assert.throws(()=>splitBill(...args));});
test('retrieves an older relevant conversation',()=>{const h=[{role:'user',text:'My project codename is Juniper'},...Array.from({length:40},()=>({role:'assistant',text:'Other topic'}))];assert.equal(relevantMemory(h,'What was the Juniper codename?')[0],h[0]);});
test('memory caps retrieval and handles multilingual words',()=>{assert.equal(relevantMemory(Array.from({length:30},()=>({text:'réunion demain'})),'réunion').length,8);assert.deepEqual(relevantMemory([],'anything'),[]);});
test('all requested app sources are represented',()=>{for(const app of ['Word','Excel','Chrome','Edge','Reading List','Voicemail'])assert.ok(apps.includes(app));});
