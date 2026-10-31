/* Shared, dependency-free schemas for deliberately saved local data. */
(function(root){
 'use strict';
 const kinds=['notes','answers','reminders'];
 function kind(value){if(!kinds.includes(value))throw Error('Unknown library collection.');return value;}
 function text(value,max,label){if(typeof value!=='string'||value.length>max)throw Error(`${label} must be text under ${max} characters.`);return value;}
 function validate(collection,value,now=new Date().toISOString()){
  kind(collection);if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Invalid library entry.');
  const id=value.id===undefined?root.crypto.randomUUID():text(value.id,100,'ID');if(!/^[\w-]{1,100}$/.test(id))throw Error('Invalid entry ID.');
  const item={id,title:text(value.title||'Untitled',200,'Title').trim()||'Untitled',updatedAt:now,pinned:value.pinned===true};
  if(collection==='reminders'){
   const due=new Date(value.dueAt);if(!Number.isFinite(due.getTime()))throw Error('Choose a valid reminder date and time.');
   item.dueAt=due.toISOString();item.completed=value.completed===true;item.body=text(value.body||'',5000,'Reminder');
  }else{
   item.body=text(value.body||'',100000,'Content');
   item.tags=Array.isArray(value.tags)?[...new Set(value.tags.map(tag=>text(tag,40,'Tag').trim()).filter(Boolean))].slice(0,12):[];
   if(collection==='answers'){item.question=text(value.question||'',5000,'Question');item.model=text(value.model||'',200,'Model');}
  }
  return item;
 }
 function query(items,search='',now=Date.now()){
  const terms=String(search).toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return items.filter(item=>terms.every(term=>[item.title,item.body,...(item.tags||[])].join(' ').toLocaleLowerCase().includes(term)))
   .sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned)||(a.dueAt&&b.dueAt?(Number(!!a.completed)-Number(!!b.completed)||new Date(a.dueAt)-new Date(b.dueAt)):new Date(b.updatedAt)-new Date(a.updatedAt)));
 }
 function due(items,now=Date.now()){return items.filter(item=>!item.completed&&new Date(item.dueAt).getTime()<=now);}
 function splitItemized({diners,items,tax=0,tipPercent=0}){
  if(!Array.isArray(diners)||diners.length<1||diners.length>50||diners.some(n=>typeof n!=='string'||!n.trim()||n.length>60))throw Error('Add 1–50 named diners.');
  if(new Set(diners.map(n=>n.trim().toLocaleLowerCase())).size!==diners.length)throw Error('Diner names must be unique.');
  if(!Array.isArray(items)||!items.length||items.length>200)throw Error('Add 1–200 bill items.');
  const cents=value=>{const n=Number(value);if(!Number.isFinite(n)||n<0||n>1000000)throw Error('Amounts must be valid and non-negative.');return Math.round((n+Number.EPSILON)*100);};
  const portions=diners.map(()=>0);let subtotal=0;
  for(const item of items){const amount=cents(item.amount);if(!Array.isArray(item.owners)||!item.owners.length||new Set(item.owners).size!==item.owners.length||item.owners.some(i=>!Number.isInteger(i)||i<0||i>=diners.length))throw Error('Assign every item to at least one diner, without duplicates.');subtotal+=amount;const base=Math.floor(amount/item.owners.length),extra=amount%item.owners.length;[...item.owners].sort((a,b)=>a-b).forEach((owner,i)=>portions[owner]+=base+(i<extra?1:0));}
  const taxCents=cents(tax),percent=Number(tipPercent);if(!Number.isFinite(percent)||percent<0||percent>1000)throw Error('Tip must be between 0% and 1000%.');const tip=cents(subtotal/100*percent/100);
  if(!subtotal&&(taxCents||tip))throw Error('Add a non-zero subtotal before allocating tax.');
  function allocate(amount){if(!subtotal)return diners.map(()=>0);const denominator=BigInt(subtotal),weights=portions.map((n,i)=>{const numerator=BigInt(amount)*BigInt(n);return {i,base:Number(numerator/denominator),fraction:numerator%denominator};});let remaining=amount-weights.reduce((s,x)=>s+x.base,0);for(const x of [...weights].sort((a,b)=>a.fraction===b.fraction?a.i-b.i:(b.fraction>a.fraction?1:-1))){if(remaining-->0)x.base++;}return weights.map(x=>x.base);}
  const taxes=allocate(taxCents),tips=allocate(tip);
  return {subtotal:subtotal/100,tax:taxCents/100,tip:tip/100,total:(subtotal+taxCents+tip)/100,shares:diners.map((name,i)=>({name,subtotal:portions[i]/100,tax:taxes[i]/100,tip:tips[i]/100,total:(portions[i]+taxes[i]+tips[i])/100}))};
 }
 function wordDiff(before,after){
  const a=String(before).match(/\s+|[^\s]+/gu)||[],b=String(after).match(/\s+|[^\s]+/gu)||[];
  if(a.length*b.length>250000)return {coarse:true,parts:[{type:'delete',text:String(before)},{type:'insert',text:String(after)}]};
  const width=b.length+1,table=new Uint16Array((a.length+1)*width);
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)table[i*width+j]=a[i]===b[j]?table[(i+1)*width+j+1]+1:Math.max(table[(i+1)*width+j],table[i*width+j+1]);
  const parts=[];function add(type,text){if(parts.length&&parts.at(-1).type===type)parts.at(-1).text+=text;else parts.push({type,text});}
  let i=0,j=0;while(i<a.length||j<b.length){if(i<a.length&&j<b.length&&a[i]===b[j]){add('same',a[i++]);j++;}else if(j<b.length&&(i===a.length||table[i*width+j+1]>=table[(i+1)*width+j]))add('insert',b[j++]);else add('delete',a[i++]);}
  return {coarse:false,parts};
 }
 const api={kinds,kind,validate,query,due,splitItemized,wordDiff};if(typeof module!=='undefined')module.exports=api;else root.SiriLibrary=api;
})(globalThis);
