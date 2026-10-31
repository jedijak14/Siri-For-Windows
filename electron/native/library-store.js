const fs=require('node:fs/promises'),path=require('node:path'),schema=require('../renderer/library');
class LibraryStore{
 constructor(file){this.file=file;this.queue=Promise.resolve();}
 async read(){try{const value=JSON.parse(await fs.readFile(this.file,'utf8'));if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Invalid library file.');return value;}catch(e){if(e.code==='ENOENT')return {notes:[],answers:[],reminders:[]};throw e;}}
 async list(collection){schema.kind(collection);await this.queue;const data=await this.read();return schema.query(Array.isArray(data[collection])?data[collection]:[]);}
 change(fn){const operation=this.queue.then(async()=>{const data=await this.read();const result=fn(data);await fs.mkdir(path.dirname(this.file),{recursive:true});const temp=this.file+'.tmp';await fs.writeFile(temp,JSON.stringify(data,null,2),'utf8');await fs.rename(temp,this.file);return result;});this.queue=operation.catch(()=>{});return operation;}
 save(collection,value){const item=schema.validate(collection,value);return this.change(data=>{const entries=Array.isArray(data[collection])?data[collection]:[];if(entries.length>=1000&&!entries.some(x=>x.id===item.id))throw Error('Library limit reached (1,000 entries per collection).');data[collection]=[...entries.filter(x=>x.id!==item.id),item];return item;});}
 remove(collection,id){schema.kind(collection);return this.change(data=>{data[collection]=(data[collection]||[]).filter(x=>x.id!==id);return true;});}
}
module.exports={LibraryStore};
