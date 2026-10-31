/* Browser preview stores only opted-in memory. Desktop uses isolated IPC instead. */
if (!window.siri) {
  const read=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}};
  const defaults={language:'auto',textModel:'',visionModel:'',memoryEnabled:false,speechRate:0,speechVolume:85,speechVoice:'',expressivity:'neutral',excludedFolders:[],excludedApps:[],hotkeyEnabled:false};
  const requests=new Map();
  const settings=()=>({...defaults,...read('siri-settings',{})});
  async function request(route,body,signal) {const r=await fetch(route,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
  const nativeOnly=async()=>{throw Error('This integration requires the Windows desktop app. No extension is needed on Windows.');};
  window.siri={
    listLibrary:async kind=>{SiriLibrary.kind(kind);return SiriLibrary.query(read('siri-library-'+kind,[]));},
    saveLibrary:async(kind,value)=>{const item=SiriLibrary.validate(kind,value),entries=read('siri-library-'+kind,[]);if(entries.length>=1000&&!entries.some(x=>x.id===item.id))throw Error('Library limit reached.');localStorage.setItem('siri-library-'+kind,JSON.stringify([...entries.filter(x=>x.id!==item.id),item]));return item;},
    removeLibrary:async(kind,id)=>{SiriLibrary.kind(kind);localStorage.setItem('siri-library-'+kind,JSON.stringify(read('siri-library-'+kind,[]).filter(x=>x.id!==id)));},
    cancelRequest:async id=>{requests.get(id)?.abort();},

    openWriting:async()=>{const panel=window.open('writing.html','siri-writing-tools','width=490,height=640');if(!panel)throw Error('Allow a popup to open the separate Writing Tools panel.');},
    writingContext:async()=>null,
    runWorkflow:nativeOnly,
    readBrowser:nativeOnly,searchInbox:nativeOnly,searchBrowserHistory:nativeOnly,replaceSelection:nativeOnly,
    listMeals:async()=>read('siri-meals',[]),
    saveMeal:async value=>{const meal={...value,id:value.id||crypto.randomUUID(),date:value.date||new Date().toISOString()};const entries=read('siri-meals',[]).filter(x=>x.id!==meal.id);entries.push(meal);localStorage.setItem('siri-meals',JSON.stringify(entries.slice(-1000)));return meal;},
    deleteMeal:async id=>localStorage.setItem('siri-meals',JSON.stringify(read('siri-meals',[]).filter(x=>x.id!==id))),
    reviewPayment:nativeOnly,

    openWindowsApp:async()=>{throw Error('Windows actions require the desktop app.');},
    listModels:()=>request('/api/models'),getSettings:async()=>settings(),
    saveSettings:async s=>{const next={...settings(),...s};localStorage.setItem('siri-settings',JSON.stringify(next));return next;},
    listHistory:async()=>settings().memoryEnabled?read('siri-history',[]):[],
    clearHistory:async()=>localStorage.removeItem('siri-history'),
    ask:async payload=>{const id=payload.requestId||crypto.randomUUID(),controller=new AbortController();requests.set(id,controller);try{const s=settings();if(payload.sourceApp&&s.excludedApps.includes(payload.sourceApp))throw Error('This app is excluded.');const history=s.memoryEnabled&&!payload.noMemory?read('siri-history',[]).filter(x=>!s.excludedApps.includes(x.sourceApp)):(payload.history||[]);const answer=await request('/api/ask',{...payload,settings:s,history:[...SiriDomain.relevantMemory(history,payload.message),...history.slice(-8)]},controller.signal);controller.signal.throwIfAborted();if(s.memoryEnabled&&!payload.noMemory){history.push({role:'user',text:payload.message,sourceApp:payload.sourceApp},{role:'assistant',text:answer.answer,sourceApp:payload.sourceApp,turn:{timestamp:answer.timestamp,mode:payload.mode,model:answer.model,sourceCards:payload.sources||[]}});localStorage.setItem('siri-history',JSON.stringify(history.slice(-500)));}return answer;}finally{requests.delete(id);}},
    writeClipboard:text=>navigator.clipboard.writeText(text),readClipboard:()=>navigator.clipboard.readText(),
    listVoices:async()=>speechSynthesis.getVoices().map(v=>v.name),
    speak:async p=>{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(p.text);u.rate=Math.max(.5,1+(p.rate||0)*.1);u.volume=(p.volume??85)/100;u.pitch=p.expressivity==='lively'?1.2:p.expressivity==='calm'?.85:1;u.voice=speechSynthesis.getVoices().find(v=>v.name===p.voice)||null;speechSynthesis.speak(u);},
    listen:async()=>{throw Error('Use your device keyboard dictation in the browser, or Windows dictation in the desktop app.');},
    chooseSearchFolder:async()=>{throw Error('Folder search is available in the Windows desktop app. You can attach exported text files here.');},
    addPrivacyExclusion:async()=>{throw Error('Folder exclusions are available in the desktop app.');},
    removePrivacyExclusion:async()=>[],onWritingShortcut:()=>()=>{},openPhotos:async()=>{throw Error('Open Photos is available on Windows.');}
  };
}
