'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const APP_NAMES={winword:'Word',excel:'Excel',powerpnt:'PowerPoint',outlook:'Outlook',onenote:'OneNote',chrome:'Chrome',msedge:'Edge'};
function appName(process){return APP_NAMES[String(process).toLowerCase()]||process;}
function validateMeal(value){
 const result={id:typeof value.id==='string'?value.id.slice(0,80):crypto.randomUUID(),date:new Date(value.date||Date.now()).toISOString(),name:String(value.name||'Meal').trim().slice(0,180),items:[]};
 if(!Array.isArray(value.items)||!value.items.length||value.items.length>50)throw Error('Add 1–50 reviewed food items.');
 for(const item of value.items){const next={name:String(item.name||'Food').slice(0,120)};for(const key of ['calories','protein','carbs','fat']){const number=Number(item[key]);if(!Number.isFinite(number)||number<0||number>100000)throw Error('Enter valid non-negative nutrition amounts.');next[key]=number;}result.items.push(next);}
 return result;
}
function paymentUrl({recipient,amount,note}){
 if(typeof recipient!=='string'||!/^@?[A-Za-z0-9_-]{1,60}$/.test(recipient))throw Error('Enter a valid Venmo username.');
 const number=Number(amount);if(!Number.isFinite(number)||number<=0||number>10000)throw Error('Payment amount must be between $0.01 and $10,000.');
 const params=new URLSearchParams({txn:'pay',recipients:recipient.replace(/^@/,''),amount:number.toFixed(2),note:String(note||'Bill split').slice(0,180)});
 return 'https://venmo.com/?'+params;
}
async function readBrowserHistory(browser,profile,query){
 if(!['Chrome','Edge'].includes(browser))throw Error('Choose Chrome or Edge.');
 if(!/^Default$|^Profile \d+$/.test(profile))throw Error('Choose Default or Profile N.');
 const base=path.join(process.env.LOCALAPPDATA||'',browser==='Chrome'?'Google/Chrome/User Data':'Microsoft/Edge/User Data',profile);
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'siri-history-'));
 let db;
 try {
  // Copy the database and its WAL, never unlock or modify the live browser store.
  for(const suffix of ['', '-wal', '-shm']){try{await fs.copyFile(path.join(base,'History'+suffix),path.join(tmp,'History'+suffix));}catch(e){if(!suffix)throw Error('Cannot read this profile history. Close the browser and try again.');if(e.code!=='ENOENT')throw e;}}
  const {DatabaseSync}=require('node:sqlite');db=new DatabaseSync(path.join(tmp,'History'));
  const safeQuery=String(query).slice(0,200).replace(/[\^%_]/g,'^$&');
  return db.prepare("SELECT title,url,datetime(last_visit_time/1000000-11644473600,'unixepoch') AS date FROM urls WHERE title LIKE ? ESCAPE '^' OR url LIKE ? ESCAPE '^' ORDER BY last_visit_time DESC LIMIT 30").all('%'+safeQuery+'%','%'+safeQuery+'%');
 }finally{db?.close();await fs.rm(tmp,{recursive:true,force:true});}
}
module.exports={appName,validateMeal,paymentUrl,readBrowserHistory};
