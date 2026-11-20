'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const panel=$('comparison-panel'), groupBar=$('ga-groups'), filters=$('ga-filters');
  const companySelect=$('ga-company'), paySelect=$('ga-pay'), search=$('ga-search');
  const table=$('ga-table'), rows=$('ga-rows'), result=$('ga-result'), more=$('ga-next');
  const notice=$('ga-notice'), retry=$('ga-retry'), clear=$('ga-clear');
  let catalog, request;
  let state={group:'short',company:'',pay:'',query:''}, limit=40;
  const opened=new Set();
  const names=new Map();
  const number=new Intl.NumberFormat('ko-KR',{minimumFractionDigits:1,maximumFractionDigits:2});
  const rate=value=>value==null?'—':number.format(value)+'%';
  const fold=value=>String(value??'').toLocaleLowerCase('ko-KR').replace(/\s+/g,'');
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function sourceLink(value,label,page=''){
    try {
      const url=new URL(value);
      if(url.protocol!=='https:'||url.username||url.password)return '';
      return '<a class="ga-source" href="'+esc(url.href)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+'</a>'+
        (page?'<small>'+esc(page)+'</small>':'');
    } catch { return ''; }
  }
  const availablePayments=p=>state.group==='short'?p.shortPays:p.pays;
  function syncOptions(){
    const relevant=catalog.products.filter(p=>(!state.group||p.group===state.group)&&(!state.company||p.company===state.company));
    const payments=[...new Set(relevant.flatMap(availablePayments))].sort((a,b)=>a.localeCompare(b,'ko',{numeric:true}));
    if(!payments.includes(state.pay))state.pay='';
    paySelect.replaceChildren(new Option('전체 납기',''),...payments.map(p=>new Option(p,p)));
    paySelect.value=state.pay;
  }
  function hydrate(){
    const p=new URL(location.href).searchParams;
    const group=p.get('category'), company=p.get('insurer');
    state={group:group==='all'?'':names.has(group)?group:'short',company:catalog.companies.includes(company)?company:'',
      pay:p.get('pay')||'',query:(p.get('q')||'').slice(0,120)};
    companySelect.value=state.company;
    search.value=state.query;
    syncOptions();
  }
  function saveState(){
    if(document.body.dataset.period!=='comparison')return;
    const url=new URL(location.href);
    for(const [key,value] of Object.entries({category:state.group||'all',insurer:state.company,pay:state.pay,q:state.query})){
      if(value)url.searchParams.set(key,value);else url.searchParams.delete(key);
    }
    history.replaceState(null,'',url);
  }
  function productMatches(p){
    if(state.company&&p.company!==state.company)return false;
    if(state.pay&&!availablePayments(p).includes(state.pay))return false;
    return fold([p.company,p.name,p.feature,p.context].join(' ')).includes(fold(state.query));
  }
  function eligibleExamples(p){
    return p.examples.filter(e=>!e.reference&&(!state.pay||e.pay===state.pay)&&
      (state.group!=='short'||p.shortPays.includes(e.pay)));
  }
  // The comparison uses one printed scenario per row. Prefer a pair of rates,
  // then the common 40-year-old male example. Preserve original PDF order.
  function mainExample(p){
    const list=eligibleExamples(p);
    const paired=e=>e.ten!=null&&e.fifteen!=null;
    const typical=e=>/40\s*세/.test(e.condition)&&/남자|남성/.test(e.person+' '+e.condition);
    return list.find(e=>paired(e)&&typical(e))||list.find(paired)||list.find(typical)||list[0];
  }
  const condition=e=>[e.person&&!e.condition.includes(e.person)?e.person:'',e.condition,e.exampleType].filter(Boolean).join(' · ');
  function detailExamples(p){
    return p.examples.filter(e=>!state.pay||e.pay===state.pay);
  }
  function evidence(p,details){
    const hasAnniversary=details.some(e=>e.anniversary!=null), columns=hasAnniversary?7:6;
    const tableRows=details.map(e=>`<tr><th scope="row">${esc(e.pay||'원문 참조')}${e.reference?'<small class="ga-reference">다른 개정본·유형 참고</small>':''}</th><td class="ga-rate">${rate(e.ten)}</td><td class="ga-rate">${rate(e.fifteen)}</td>${hasAnniversary?`<td class="ga-rate">${rate(e.anniversary)}</td>`:''}<td class="ga-rate">${rate(e.twenty)}</td><td>${esc(condition(e)||e.position)}${e.condition&&e.position?`<small>${esc(e.position)}</small>`:''}</td><td>${sourceLink(e.source,'공식 PDF',e.page)}</td></tr>`).join('');
    const known=details.length?`<div class="ga-evidence-scroll" role="region" tabindex="0" aria-label="${esc(p.name)} 공식 환급률 예시"><table class="ga-evidence-table"><thead><tr><th scope="col">예시 납기</th><th scope="col">10년</th><th scope="col">15년</th>${hasAnniversary?'<th scope="col">10년+1일</th>':''}<th scope="col">20년</th><th scope="col">원문 예시 조건</th><th scope="col">공시 근거</th></tr></thead><tbody>${tableRows||`<tr><td colspan="${columns}">해당 예시는 없습니다.</td></tr>`}</tbody></table></div>`:'';
    return `<div class="ga-detail-inner"><p>${esc(p.coverage)}${p.note?' · '+esc(p.note):''}</p>${known}</div>`;
  }
  function productRow(p, showAnniversary){
    const e=mainExample(p), details=detailExamples(p), expanded=opened.has(p.id);
    const displayPay=p.group==='short'&&state.group==='short'?p.shortPays.join(' · '):p.payLabel;
    const link=e?sourceLink(e.source,'공식 PDF',e.page):sourceLink(p.source,'공시 문서');
    const conditionLabel=e?condition(e)||e.position:state.pay?'이 납기 공식 예시 미확인':
      state.group==='short'&&p.examples.some(x=>!x.reference)?'단기납 공식 예시 미확인':p.coverage;
    const detailButton=details.length?`<button type="button" class="ga-expand" data-product-id="${esc(p.id)}" aria-expanded="${expanded}" aria-controls="ga-detail-${esc(p.id)}" aria-label="${esc(p.name)} 공식 예시 ${expanded?'접기':'보기'}">${expanded?'예시 접기':'예시 '+details.length+'건'}</button>`:'';
    return `<tr class="ga-product"><td class="ga-insurer">${esc(p.company)}</td><th scope="row" class="ga-product-name">${esc(p.name)}<small>${esc(names.get(p.group))}${p.currency?' · '+esc(p.currency):''}</small></th><td class="ga-pay">${esc(state.pay||displayPay)}${e?.pay?`<small>표의 예시 ${esc(e.pay)}</small>`:''}</td><td class="ga-rate">${rate(e?.ten)}</td><td class="ga-rate">${rate(e?.fifteen)}</td>${showAnniversary?`<td class="ga-rate">${rate(e?.anniversary)}</td>`:''}<td class="ga-features"><strong>${esc(p.feature||'상품요약서 참조')}</strong>${p.context?`<small>${esc(p.context)}</small>`:''}</td><td class="ga-proof"><span>${esc(conditionLabel)}</span>${link}${detailButton}</td></tr>${details.length?`<tr class="ga-detail-row" id="ga-detail-${esc(p.id)}" ${expanded?'':'hidden'}><td colspan="${showAnniversary?8:7}">${expanded?evidence(p,details):''}</td></tr>`:''}`;
  }
  function render(){
    const matched=catalog.products.filter(productMatches);
    const items=matched.filter(p=>!state.group||p.group===state.group);
    for(const button of groupBar.querySelectorAll('button')){
      const group=button.dataset.group;
      button.setAttribute('aria-pressed',String(state.group===group));
      button.querySelector('small').textContent=catalog.products.filter(p=>!group||p.group===group).length;
    }
    result.textContent=(state.group?names.get(state.group):'전체')+' · '+items.length+'개 상품·유형';
    const hasAnniversary=items.some(p=>mainExample(p)?.anniversary!=null);
    $('ga-anniversary').hidden=!hasAnniversary;
    rows.innerHTML=items.slice(0,limit).map(p=>productRow(p,hasAnniversary)).join('');
    table.hidden=!items.length;
    notice.textContent=items.length?'':'조건에 맞는 상품이 없습니다. 검색어나 필터를 바꿔보세요.';
    notice.hidden=items.length>0;
    more.hidden=items.length<=limit;
    more.textContent='상품 더 보기 ('+Math.min(items.length,limit)+'/'+items.length+')';
    clear.disabled=!(state.pay||state.company||state.query);
    saveState();
  }
  function resetPage(){
    limit=40;
    opened.clear();
    render();
  }
  async function activate(){
    try {
      retry.hidden=true;
      if(!catalog){
        request ||= fetch('data/ga-comparison.json',{cache:'no-cache'}).then(r=>{
          if(!r.ok)throw new Error('Comparison data is unavailable');
          return r.json();
        });
        const data=await request;
        if(data.version!==1||!Array.isArray(data.products))throw new Error('Invalid comparison data');
        if(!catalog){
          catalog=data;
          for(const group of data.groups)names.set(group.id,group.label);
          groupBar.innerHTML=[...data.groups,{id:'',label:'전체'}].map(g=>
            `<button type="button" data-group="${esc(g.id)}" aria-pressed="false">${esc(g.label)} <small></small></button>`).join('');
          companySelect.append(...data.companies.map(x=>new Option(x,x)));
          $('ga-date').textContent=data.date.replaceAll('-','.');
          $('ga-scope').textContent=data.companies.length+'개 보험사 · '+data.products.length+'개 상품·유형';
          filters.hidden=false;
        }
      }
      if(panel.hidden)return;
      hydrate();
      resetPage();
    } catch {
      request=null;
      if(panel.hidden)return;
      notice.textContent='비교장표를 불러오지 못했습니다.';
      notice.hidden=false;
      retry.hidden=false;
    }
  }
  groupBar.addEventListener('click',event=>{
    const button=event.target.closest('button[data-group]');
    if(!button||!catalog)return;
    state.group=button.dataset.group;
    syncOptions();
    resetPage();
  });
  filters.addEventListener('submit',e=>e.preventDefault());
  companySelect.addEventListener('change',()=>{state.company=companySelect.value;syncOptions();resetPage();});
  paySelect.addEventListener('change',()=>{state.pay=paySelect.value;resetPage();});
  search.addEventListener('input',()=>{state.query=search.value.trim().slice(0,120);resetPage();});
  clear.addEventListener('click',()=>{
    state.company=state.pay=state.query='';
    companySelect.value=search.value='';
    syncOptions();
    resetPage();
  });
  more.addEventListener('click',()=>{limit+=40;render();});
  retry.addEventListener('click',activate);
  rows.addEventListener('click',event=>{
    const button=event.target.closest('[data-product-id]');
    if(!button)return;
    const id=button.dataset.productId, p=catalog.products.find(p=>p.id===id);
    const detail=$('ga-detail-'+id);
    const next=detail.hidden;
    if(next){opened.add(id);detail.cells[0].innerHTML=evidence(p,detailExamples(p));}
    else opened.delete(id);
    detail.hidden=!next;
    button.setAttribute('aria-expanded',String(next));
    button.setAttribute('aria-label',p.name+' 공식 예시 '+(next?'접기':'보기'));
    button.textContent=next?'예시 접기':'예시 '+detailExamples(p).length+'건';
  });
  window.addEventListener('brief:mode',event=>{if(event.detail.mode==='comparison')activate();});
})();
