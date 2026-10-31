/* Pure functions shared by desktop and browser. */
(function(root) {
  const apps = ['Word','Excel','PowerPoint','Outlook','OneNote','Chrome','Edge','Photos','Calendar','Voicemail','Reading List'];
  function splitBill(items, tax, tip, people) {
    if (!Number.isInteger(people) || people < 1 || people > 100) throw Error('Choose 1–100 people.');
    const cents = value => { const n=Number(value); if(!Number.isFinite(n)||n<0||n>1000000) throw Error('Enter a valid, non-negative amount.'); return Math.round(n*100); };
    const subtotal=items.reduce((s,v)=>s+cents(v),0), taxCents=cents(tax);
    const tipCents=cents(subtotal/100 * Number(tip)/100);
    const total=subtotal+taxCents+tipCents, base=Math.floor(total/people), remainder=total%people;
    return {subtotal:subtotal/100,tax:taxCents/100,tip:tipCents/100,total:total/100,shares:Array.from({length:people},(_,i)=>(base+(i<remainder?1:0))/100)};
  }
  function relevantMemory(history, query) {
    const terms=query.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu)||[];
    return history.map((x,i)=>({x,i,score:terms.reduce((s,t)=>s+(String(x.text).toLowerCase().includes(t)?1:0),0)}))
      .filter(x=>x.score).sort((a,b)=>b.score-a.score||b.i-a.i).slice(0,8).sort((a,b)=>a.i-b.i).map(x=>x.x);
  }
  const api={apps,splitBill,relevantMemory}; if(typeof module!=='undefined') module.exports=api; else root.SiriDomain=api;
})(globalThis);
