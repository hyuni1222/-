'use strict';
/* Pure product filtering and publication rules, shared by UI and checks. */
((root)=>{
  const categories=['종신','연금','정기'];
  const number=value=>typeof value==='number'&&Number.isFinite(value);
  const safeURL=value=>{try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}};
  const payLabel=value=>typeof value==='number'?value+'년납':String(value);
  function payKey(value){
    if(typeof value==='number')return 'years:'+value;
    const text=String(value);
    const age=text.match(/^(\d+)세납$/);if(age)return 'age:'+age[1];
    const years=text.match(/^(\d+)년납\(예시\)$/);if(years)return 'years:'+years[1];
    if(text.startsWith('전기납'))return 'full';
    return null;
  }
  function payOptions(data){
    const keys=[...new Set(data.products.flatMap(p=>p.pays.map(payKey)).filter(Boolean))];
    return keys.sort((a,b)=>{
      const rank=x=>x.startsWith('years:')?0:x.startsWith('age:')?1:2;
      return rank(a)-rank(b)||(parseInt(a.split(':')[1])||0)-(parseInt(b.split(':')[1])||0);
    }).map(value=>({value,label:value==='full'?'전기납':value.split(':')[1]+(value.startsWith('age:')?'세납':'년납')}));
  }
  function filterProducts(data,state){
    const q=String(state.query||'').trim().toLocaleLowerCase('ko-KR');
    return data.products.filter(p=>p.channel_status==='ga_material_found'&&
      (!state.insurer||p.insurer===state.insurer)&&(!state.category||p.category===state.category)&&
      (!state.pay||p.pays.some(x=>payKey(x)===state.pay))&&
      (!q||[p.insurer,p.name,p.feature,p.analysis,p.after_use,p.currency].join(' ').toLocaleLowerCase('ko-KR').includes(q)));
  }
  function visibleExamples(product,state){
    return product.examples.filter(e=>
      (e.version_status==='current_document'||state.previous===true)&&
      (!state.pay||payKey(e.pay)===state.pay));
  }
  function formatRate(value){return number(value)?new Intl.NumberFormat('ko-KR',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:2}).format(value):'미확인';}
  function readState(params,data){
    const insurer=params.get('insurer')||'',category=params.get('category')||'',pay=params.get('pay')||'';
    const ids=new Set(data.products.map(p=>p.id));
    return {insurer:data.insurers.includes(insurer)?insurer:'',category:categories.includes(category)?category:'',
      pay:payOptions(data).some(p=>p.value===pay)?pay:'',query:(params.get('q')||'').slice(0,120),
      previous:params.get('previous')==='1',compare:[...new Set((params.get('compare')||'').split(','))].filter(id=>ids.has(id)).slice(0,3)};
  }
  function writeState(url,state){
    const next=new URL(url);next.searchParams.set('view','products');next.searchParams.delete('date');next.searchParams.delete('period');
    for(const [key,value] of Object.entries({insurer:state.insurer,category:state.category,pay:state.pay,q:state.query,
      previous:state.previous?'1':'',compare:state.compare?.join(',')})){
      if(value)next.searchParams.set(key,value);else next.searchParams.delete(key);
    }
    next.hash='';return next;
  }
  const api={categories,number,safeURL,payLabel,payKey,payOptions,filterProducts,visibleExamples,formatRate,readState,writeState};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.GAProductModel=api;
})(typeof globalThis!=='undefined'?globalThis:this);
