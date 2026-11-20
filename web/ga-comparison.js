'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const panel=$('comparison-panel'), groupBar=$('ga-groups'), filters=$('ga-filters');
  const companySelect=$('ga-company'), paySelect=$('ga-pay'), search=$('ga-search');
  const table=$('ga-table'), rows=$('ga-rows'), result=$('ga-result'), more=$('ga-next');
  const notice=$('ga-notice'), retry=$('ga-retry'), clear=$('ga-clear');
  const mobile=$('ga-mobile'), mobileList=$('ga-mobile-list'), sheet=$('ga-sheet'), sheetContent=$('ga-sheet-content');
  const filterToggle=$('ga-filter-toggle');
  let catalog, request;
  let state={group:'short',company:'',pay:'',query:''}, limit=40;
  const opened=new Set();
  const names=new Map();
  const number=new Intl.NumberFormat('ko-KR',{minimumFractionDigits:1,maximumFractionDigits:2});
  const rate=(value,qualifier)=>value==null?'—':(qualifier?esc(qualifier)+' ':'')+number.format(value)+'%';
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
  function mobileSourceLinks(value,page=''){
    const original=sourceLink(value,'원본 다운로드');
    if(!original)return '';
    const url=new URL(value);
    const officialPDF=(url.host==='pub.insure.or.kr'&&url.pathname==='/FileDown.do')||
      (url.host==='brand.metlife.co.kr'&&url.pathname==='/pn/mcvrgProd/mcvrgProdDownloadFile.do');
    if(!officialPDF)return sourceLink(value,'공시 문서',page);
    const viewer=new URL('https://docs.google.com/gview');
    viewer.searchParams.set('embedded','true');
    viewer.searchParams.set('url',url.href);
    const preview=sourceLink(viewer.href,'PDF 새 탭에서 보기');
    return '<div class="ga-source-actions">'+preview+original+'</div>'+
      (page?'<small>'+esc(page)+'</small>':'');
  }
  function refundSource(e,mobile=false){
    if(!e.newsletter)return mobile?mobileSourceLinks(e.source,e.page):sourceLink(e.source,'공식 PDF',e.page);
    return `<a class="ga-source ga-newsletter-source" href="${esc(e.newsletter)}" target="_blank" rel="noopener noreferrer">11월 소식지</a>`+
      (e.page?`<small>${esc(e.page)}</small>`:'');
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
  // The comparison uses one printed scenario per row. Prefer a pair of rates,
  // then the common 40-year-old male example within the same source tier.
  function preferredExample(list){
    const paired=e=>e.ten!=null&&e.fifteen!=null;
    const typical=e=>/40\s*세/.test(e.condition)&&/남자|남성/.test(e.person+' '+e.condition);
    return list.find(e=>paired(e)&&typical(e))||list.find(paired)||list.find(typical)||list[0];
  }
  function mainExample(p){
    const fits=e=>(!state.pay||e.pay===state.pay)&&(state.group!=='short'||p.shortPays.includes(e.pay));
    return preferredExample(p.examples.filter(e=>!e.reference&&fits(e)))||
      preferredExample(p.newsletterExamples.filter(fits));
  }
  const condition=e=>[e.person&&!e.condition.includes(e.person)?e.person:'',e.condition,e.exampleType].filter(Boolean).join(' · ');
  function detailExamples(p){
    const visible=e=>!state.pay||e.pay===state.pay;
    const official=p.examples.filter(visible);
    const examples=[...official.filter(e=>!e.reference),...p.newsletterExamples.filter(visible),...official.filter(e=>e.reference)];
    const primary=mainExample(p);
    return primary?[primary,...examples.filter(e=>e!==primary)]:examples;
  }
  function displayPayment(p){
    if(state.pay)return state.pay;
    return p.group==='short'&&state.group==='short'?p.shortPays.join(' · '):p.payLabel;
  }
  function missingExample(p){
    if(state.pay)return '이 납기 환급률 예시 미확인';
    return state.group==='short'&&p.examples.some(x=>!x.reference)?'단기납 환급률 예시 미확인':p.coverage;
  }
  function evidence(p,details){
    const hasAnniversary=details.some(e=>e.anniversary!=null);
    const tableRows=details.map(e=>`<tr><th scope="row">${esc(e.pay||'원문 참조')}${e.reference?'<small class="ga-reference">다른 개정본·유형 참고</small>':''}</th><td class="ga-rate">${rate(e.ten,e.qualifier)}</td><td class="ga-rate">${rate(e.fifteen,e.qualifier)}</td>${hasAnniversary?`<td class="ga-rate">${rate(e.anniversary,e.qualifier)}</td>`:''}<td class="ga-rate">${rate(e.twenty,e.qualifier)}</td><td>${esc(condition(e)||e.position)}${e.condition&&e.position?`<small>${esc(e.position)}</small>`:''}</td><td>${refundSource(e)}</td></tr>`).join('');
    return `<div class="ga-detail-inner">${p.note?`<p>${esc(p.note)}</p>`:''}<div class="ga-evidence-scroll" role="region" tabindex="0" aria-label="${esc(p.name)} 환급률 예시"><table class="ga-evidence-table"><thead><tr><th scope="col">예시 납기</th><th scope="col">10년</th><th scope="col">15년</th>${hasAnniversary?'<th scope="col">10년+1일</th>':''}<th scope="col">20년</th><th scope="col">원문 예시 조건</th><th scope="col">출처</th></tr></thead><tbody>${tableRows}</tbody></table></div></div>`;
  }
  function detailLabel(details){
    const newsletterCount=details.filter(e=>e.newsletter).length;
    return '예시 '+details.length+'건'+(newsletterCount?' · 소식지 '+newsletterCount+'건':'');
  }
  function productRow(p, showAnniversary){
    const e=mainExample(p), details=detailExamples(p), expanded=opened.has(p.id);
    const link=e?refundSource(e):sourceLink(p.source,'공시 문서');
    const conditionLabel=e?condition(e)||e.position:missingExample(p);
    const detailButton=details.length?`<button type="button" class="ga-expand" data-product-id="${esc(p.id)}" aria-expanded="${expanded}" aria-controls="ga-detail-${esc(p.id)}" aria-label="${esc(p.name)} ${expanded?'예시 접기':detailLabel(details)}">${expanded?'예시 접기':detailLabel(details)}</button>`:'';
    return `<tr class="ga-product"><td class="ga-insurer">${esc(p.company)}</td><th scope="row" class="ga-product-name">${esc(p.name)}<small>${esc(names.get(p.group))}${p.currency?' · '+esc(p.currency):''}</small></th><td class="ga-pay">${esc(displayPayment(p))}${e?.pay?`<small>표의 예시 ${esc(e.pay)}</small>`:''}</td><td class="ga-rate">${rate(e?.ten,e?.qualifier)}</td><td class="ga-rate">${rate(e?.fifteen,e?.qualifier)}</td>${showAnniversary?`<td class="ga-rate">${rate(e?.anniversary,e?.qualifier)}</td>`:''}<td class="ga-features"><strong>${esc(p.feature||'상품요약서 참조')}</strong>${p.context?`<small>${esc(p.context)}</small>`:''}</td><td class="ga-proof"><span>${esc(conditionLabel)}</span>${link}${detailButton}</td></tr>${details.length?`<tr class="ga-detail-row" id="ga-detail-${esc(p.id)}" ${expanded?'':'hidden'}><td colspan="${showAnniversary?8:7}">${expanded?evidence(p,details):''}</td></tr>`:''}`;
  }
  function mobileRow(p){
    const e=mainExample(p);
    const subtitle=e?.pay?' · '+e.pay:p.currency?' · '+p.currency:'';
    const supplemental=p.newsletterExamples.some(e=>!state.pay||e.pay===state.pay);
    const newsletterLabel=e?.newsletter?'11월 소식지':supplemental?'소식지 예시 있음':'';
    const anniversary=e?.anniversary!=null?`<small class="ga-mobile-anniversary">10년+1일 ${rate(e.anniversary,e.qualifier)}</small>`:'';
    return `<li><button type="button" class="ga-mobile-row" data-ga-open="${esc(p.id)}" aria-haspopup="dialog" aria-controls="ga-sheet">
      <span class="ga-mobile-product"><small>${esc(p.company+subtitle)}</small><strong>${esc(p.name)}</strong>${anniversary}${newsletterLabel?`<small class="ga-newsletter-source">${newsletterLabel}</small>`:''}</span>
      <span class="ga-mobile-rate"><span class="ga-a11y">10년 환급률 </span>${e?.ten!=null&&e.qualifier?`<small class="ga-mobile-qualifier">${esc(e.qualifier)}</small>`:''}${rate(e?.ten)}</span>
      <span class="ga-mobile-rate"><span class="ga-a11y">15년 환급률 </span>${e?.fifteen!=null&&e.qualifier?`<small class="ga-mobile-qualifier">${esc(e.qualifier)}</small>`:''}${rate(e?.fifteen)}</span>
    </button></li>`;
  }
  function sheetExample(e,selected){
    const metrics=[['10년',e.ten],['15년',e.fifteen]];
    if(e.anniversary!=null)metrics.push(['10년+1일',e.anniversary]);
    if(e.twenty!=null)metrics.push(['20년',e.twenty]);
    const label=e.newsletter?'<span class="ga-newsletter-source">11월 소식지 예시</span>':'<span>상품요약서</span>';
    return `<li class="ga-sheet-example"><div class="ga-sheet-example-heading"><strong>${esc(e.pay||'환급률 예시')}</strong>${label}${e.reference?'<span class="ga-sheet-reference">다른 개정본·유형 참고</span>':selected?'<span>비교 목록에 표시</span>':''}</div>
      <dl class="ga-sheet-metrics">${metrics.map(([term,value])=>`<div><dt>${term}</dt><dd>${rate(value,e.qualifier)}</dd></div>`).join('')}</dl>
      <p>${esc(condition(e)||e.position)}</p>
      ${refundSource(e,true)}
    </li>`;
  }
  function openSheet(product){
    const primary=mainExample(product);
    const examples=detailExamples(product);
    const note=product.note?.includes('납기별 설계 탭')?'':product.note;
    $('ga-sheet-company').textContent=[product.company,names.get(product.group),product.currency].filter(Boolean).join(' · ');
    $('ga-sheet-title').textContent=product.name;
    sheetContent.innerHTML=`<section class="ga-sheet-summary" aria-label="상품 특징">
      <p><strong>납기</strong> ${esc(displayPayment(product))}</p>
      ${product.feature?`<p><strong>${esc(product.feature)}</strong></p>`:''}
      ${product.context?`<p>${esc(product.context)}</p>`:''}
    </section><h4>해약환급률 예시</h4>
    ${!primary?`<p class="ga-sheet-status">${esc(missingExample(product))}</p>`:''}
    ${examples.length?`<ul class="ga-sheet-examples">${examples.map(e=>sheetExample(e,e===primary)).join('')}</ul>`:mobileSourceLinks(product.source)}
    ${note?`<p class="ga-sheet-status">${esc(note)}</p>`:''}`;
    sheet.showModal();
    sheetContent.scrollTop=0;
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
    const visible=items.slice(0,limit);
    rows.innerHTML=visible.map(p=>productRow(p,hasAnniversary)).join('');
    mobileList.innerHTML=visible.map(mobileRow).join('');
    mobile.hidden=!items.length;
    table.hidden=!items.length;
    notice.textContent=items.length?'':'조건에 맞는 상품이 없습니다. 검색어나 필터를 바꿔보세요.';
    notice.hidden=items.length>0;
    more.hidden=items.length<=limit;
    more.textContent='상품 더 보기 ('+Math.min(items.length,limit)+'/'+items.length+')';
    const activeFilters=[state.pay,state.company,state.query].filter(Boolean).length;
    $('ga-filter-label').textContent=activeFilters?'검색·필터 '+activeFilters+'개 적용':'검색·필터';
    clear.disabled=!activeFilters;
    saveState();
  }
  function resetPage(){
    limit=40;
    opened.clear();
    render();
  }
  function fetchData(path){
    return fetch(path,{cache:'no-cache'}).then(r=>{
      if(!r.ok)throw new Error('Comparison data is unavailable');
      return r.json();
    });
  }
  function addNewsletterExamples(data,newsletter){
    for(const p of data.products){
      const entry=newsletter.products?.[p.id];
      p.newsletterExamples=[];
      if(!/^\d{4}-\d{2}$/.test(newsletter.edition)||!entry||!/^[a-z]+-\d{2}\.jpg$/.test(entry.image))continue;
      const source='assets/newsletters/'+newsletter.edition+'/'+entry.image;
      p.newsletterExamples=entry.examples.map(e=>({...e,newsletter:source,page:entry.page}));
      const pays=[...new Set([...p.pays,...p.newsletterExamples.map(e=>e.pay)])];
      if(pays.length>p.pays.length)p.payLabel=pays.sort((a,b)=>a.localeCompare(b,'ko',{numeric:true})).join(' · ');
      p.pays=pays;
      if(entry.name)p.name=entry.name;
      if(entry.note)p.note=entry.note;
    }
  }
  async function activate(){
    try {
      retry.hidden=true;
      if(!catalog){
        request ||= Promise.all([
          fetchData('data/ga-comparison.json'),
          fetchData('data/ga-newsletter-refunds.json').catch(()=>({}))
        ]);
        const [data,newsletter]=await request;
        if(data.version!==1||!Array.isArray(data.products))throw new Error('Invalid comparison data');
        if(!catalog){
          addNewsletterExamples(data,newsletter);
          catalog=data;
          for(const group of data.groups)names.set(group.id,group.label);
          groupBar.innerHTML=[...data.groups,{id:'',label:'전체'}].map(g=>
            `<button type="button" data-group="${esc(g.id)}" aria-pressed="false">${esc(g.label)} <small></small></button>`).join('');
          companySelect.append(...data.companies.map(x=>new Option(x,x)));
          $('ga-date').textContent=data.date.replaceAll('-','.');
          $('ga-scope').textContent=data.companies.length+'개 보험사 · '+data.products.length+'개 상품·유형';
          filters.hidden=false;
          filterToggle.hidden=false;
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
  filterToggle.addEventListener('click',()=>{
    const open=filters.classList.toggle('ga-filters-open');
    filterToggle.setAttribute('aria-expanded',String(open));
  });
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
  sheet.addEventListener('click',event=>{if(event.target===sheet)sheet.close();});
  mobileList.addEventListener('click',event=>{
    const button=event.target.closest('[data-ga-open]');
    if(!button)return;
    const product=catalog.products.find(p=>p.id===button.dataset.gaOpen);
    if(product)openSheet(product);
  });
  rows.addEventListener('click',event=>{
    const button=event.target.closest('[data-product-id]');
    if(!button)return;
    const id=button.dataset.productId, p=catalog.products.find(p=>p.id===id);
    const detail=$('ga-detail-'+id);
    const next=detail.hidden;
    const details=detailExamples(p);
    if(next){opened.add(id);detail.cells[0].innerHTML=evidence(p,details);}
    else opened.delete(id);
    detail.hidden=!next;
    button.setAttribute('aria-expanded',String(next));
    const label=next?'예시 접기':detailLabel(details);
    button.setAttribute('aria-label',p.name+' '+label);
    button.textContent=label;
  });
  window.addEventListener('brief:mode',event=>{
    if(event.detail.mode==='comparison')activate();
    else if(sheet.open)sheet.close();
  });
})();
