'use strict';
(()=>{
  const M=window.GAProductModel,$=id=>document.getElementById(id);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data=null,sources=new Map(),state=null,loading=null,limit=12;
  const facts=[['확인된 납입기간','pays'],['보험기간','term'],['자료상 심사·유형','form'],['상품 구조','feature'],
    ['자금 활용·연금개시 시점','available_from'],['한도·수령 방식','limit'],['활용 후 보장·연금 변화','after_use'],['비교 해석','analysis']];
  const previousCount=p=>p.examples.filter(e=>e.version_status!=='current_document').length;
  function sourceLink(id){
    const s=sources.get(id);if(!s)return '';
    const title=esc(s.title),url=M.safeURL(s.url);
    return `<li>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`:title}<span>${esc(s.kind)} · ${esc(s.date)}</span>${s.link_note?`<small>${esc(s.link_note)}</small>`:''}</li>`;
  }
  function rateNotice(p){
    if(p.rate_status==='official_not_provided')return '공식 안내상 해약환급금 예시표 미제공 유형입니다. 0% 또는 최저환급금 보증을 뜻하지 않습니다.';
    const old=previousCount(p);
    if(!state.previous&&old)return `이전·현행 미대조 공시 예시 ${old}건이 있습니다. 위의 ‘이전 공시 예시도 보기’를 선택하면 조건과 함께 확인할 수 있습니다.`;
    if(state.pay&&p.examples.length)return '선택한 납기의 공식 환급예시를 확보하지 못했습니다. 납입기간을 전체로 바꾸면 다른 납기의 예시를 확인할 수 있습니다.';
    return '공식 환급예시 대조 중입니다. 확인되지 않은 값을 0%로 표시하거나 추정하지 않습니다.';
  }
  function rateRows(p){
    const examples=M.visibleExamples(p,state);
    if(!examples.length)return `<p class="product-rate-note">${esc(rateNotice(p))}</p>`;
    return `<div class="product-rate-scroll" tabindex="0" role="region" aria-label="${esc(p.name)} 납기별 환급예시"><table class="product-rates"><caption>가입 후 경과기간별 해약환급률 · ${esc(p.currency)} 기준</caption><thead><tr><th scope="col">납기·자료</th><th scope="col">10년</th><th scope="col">15년</th><th scope="col">예시 조건</th></tr></thead><tbody>${examples.map(e=>`<tr><th scope="row">${esc(M.payLabel(e.pay))}<span class="product-example-tag ${e.version_status==='current_document'?'':'previous'}">${e.version_status==='current_document'?'현행 공시 예시':'이전·현행 미대조 예시'}</span><small>문서 ${esc(e.document_date)}</small></th><td class="product-rate-value">${M.formatRate(e.rate10)}</td><td class="product-rate-value">${M.formatRate(e.rate15)}</td><td><p>${esc(e.age)} · ${esc(e.form)} · ${esc(e.amount)}</p><p>${esc(e.interest)}</p><small>${esc(e.note)}</small><a class="product-inline-source" href="${esc(M.safeURL(sources.get(e.source_id)?.url)||'#')}" target="_blank" rel="noopener noreferrer">공식 상품요약서</a>${e.version_source_id?`<a class="product-inline-source" href="${esc(M.safeURL(sources.get(e.version_source_id)?.url)||'#')}" target="_blank" rel="noopener noreferrer">판매기간 대조 ${esc(e.version_checked_on)}</a>`:''}</td></tr>`).join('')}</tbody></table></div><p class="product-rate-note">개인 가입설계의 확정값이 아닙니다. 이율·운용 가정, 보너스 시점과 인출 여부가 바뀌면 결과도 달라집니다.</p>`;
  }
  function card(p){
    const chosen=state.compare.includes(p.id),examples=M.visibleExamples(p,state);
    const rateLabel=examples.length?'공식 공시 예시 '+examples.length+'건':!state.previous&&previousCount(p)?'이전 공시 예시 '+previousCount(p)+'건':p.rate_status==='official_not_provided'?'환급예시 미제공':'공식 환급예시 확인 중';
    return `<article class="product-card" id="product-${esc(p.id)}"><header><div class="product-card-meta"><span>${esc(p.insurer)}</span><span>${esc(p.category)} · ${esc(p.currency)}</span></div><h3>${esc(p.name)}</h3><p class="product-version">${esc(p.version)}</p></header><p class="product-feature">${esc(p.feature)}</p><div class="product-pay-tags" aria-label="자료에서 확인한 납기">${p.pays.map(v=>`<span>${esc(M.payLabel(v))}</span>`).join('')}</div><p class="product-pay-basis">${esc(p.pay_basis)}</p><dl class="product-quick-facts"><div><dt>자금 활용 시점</dt><dd>${esc(p.available_from)}</dd></div><div><dt>활용 후 보장</dt><dd>${esc(p.after_use)}</dd></div></dl><div class="product-card-actions"><span class="product-rate-status">${esc(rateLabel)}</span><button type="button" data-compare="${esc(p.id)}" aria-pressed="${chosen}" aria-label="${esc(p.name)} ${chosen?'비교에서 제외':'비교에 추가'}">${chosen?'선택됨':'비교에 담기'}</button></div><details class="product-detail"><summary>조건·환급예시·출처</summary><div class="product-detail-body"><h4>납기별 해약환급 예시</h4>${rateRows(p)}<dl class="product-all-facts">${facts.map(([label,key])=>`<div><dt>${label}</dt><dd>${esc(key==='pays'?p.pays.map(M.payLabel).join(' / '):p[key])}</dd></div>`).join('')}</dl><p class="product-missing"><strong>추가 확인</strong>${esc(p.missing)}</p><p class="product-channel-note">${esc(p.channel_note)}</p><details class="product-sources"><summary>근거 자료 ${p.source_ids.length}건</summary><ul>${p.source_ids.map(sourceLink).join('')}</ul></details></div></details></article>`;
  }
  function saveURL(){if(document.body.dataset.period==='products')history.replaceState(null,'',M.writeState(location.href,state));}
  function renderCompareTray(){
    const chosen=state.compare.map(id=>data.products.find(p=>p.id===id)).filter(Boolean);
    $('product-compare-tray').hidden=!chosen.length;
    $('product-compare-selected').innerHTML=chosen.map(p=>`<button type="button" data-remove="${esc(p.id)}" aria-label="${esc(p.name)} 비교에서 제외">${esc(p.name)} <span aria-hidden="true">×</span></button>`).join('');
    $('product-compare-open').disabled=chosen.length<2;
    $('product-compare-open').textContent=chosen.length+'개 상품 비교';
  }
  function render(){
    if(!data)return;
    const expanded=new Set([...$('product-list').querySelectorAll('.product-detail[open]')].map(el=>el.closest('article').id));
    const items=M.filterProducts(data,state),shown=items.slice(0,limit);
    $('product-result-count').textContent=items.length+'개 상품';
    $('product-categories').querySelectorAll('[data-category]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.category===state.category)));
    $('product-list').innerHTML=shown.map(card).join('')||`<div class="product-empty"><h3>${state.insurer==='흥국생명'?'GA 취급 확인을 진행 중입니다.':'조건에 맞는 상품이 없습니다.'}</h3><p>${state.insurer==='흥국생명'?'흥국생명은 회사 상품 판매는 확인했으나 GA 취급 근거를 추가 확인하고 있습니다.':'보험사·상품 종류·납입기간 또는 검색어를 바꿔보세요.'}</p><button type="button" data-reset>전체 상품 보기</button></div>`;
    $('product-list').querySelectorAll('article').forEach(el=>{if(expanded.has(el.id))el.querySelector('.product-detail').open=true;});
    $('product-more').hidden=shown.length>=items.length;
    $('product-more').textContent='상품 더 보기 ('+shown.length+'/'+items.length+')';
    renderCompareTray();saveURL();
  }
  function changeFilters(){
    state.insurer=$('product-insurer').value;state.pay=$('product-pay').value;
    state.query=$('product-query').value.trim().slice(0,120);state.previous=$('product-previous').checked;
    limit=12;render();
  }
  function reset(){
    state={...state,insurer:'',category:'',pay:'',query:'',previous:false};limit=12;
    $('product-insurer').value='';$('product-pay').value='';$('product-query').value='';$('product-previous').checked=false;
    render();
  }
  function toggleCompare(id){
    const index=state.compare.indexOf(id);
    if(index>=0)state.compare.splice(index,1);
    else if(state.compare.length<3)state.compare.push(id);
    else{$('product-feedback').textContent='한 번에 최대 3개까지 비교할 수 있습니다. 담은 상품을 하나 해제해주세요.';return;}
    $('product-feedback').textContent=state.compare.length+'개 상품을 비교에 담았습니다.';
    // Keep expanded product details and scroll position when a selection changes.
    document.querySelectorAll('[data-compare]').forEach(b=>{const selected=state.compare.includes(b.dataset.compare);b.setAttribute('aria-pressed',String(selected));b.textContent=selected?'선택됨':'비교에 담기';const p=data.products.find(p=>p.id===b.dataset.compare);b.setAttribute('aria-label',p.name+' '+(selected?'비교에서 제외':'비교에 추가'));});
    renderCompareTray();saveURL();
  }
  function openComparison(){
    const chosen=state.compare.map(id=>data.products.find(p=>p.id===id)).filter(Boolean);if(chosen.length<2)return;
    const cells=key=>chosen.map(p=>`<td>${key==='refund'?rateRows(p):esc(key==='pays'?p.pays.map(M.payLabel).join(' / '):p[key])}</td>`).join('');
    const rows=[['납입기간','pays'],['보험기간','term'],['통화','currency'],['상품 구조','feature'],['활용 시점','available_from'],['한도·수령 방식','limit'],['활용 후 보장·연금','after_use'],['10년·15년 환급예시','refund'],['자료 버전','version'],['추가 확인','missing']];
    $('product-comparison-body').innerHTML=`<p class="product-comparison-note">${new Set(chosen.map(p=>p.currency)).size>1?'원화·달러 상품이 함께 선택되었습니다. ':''}${new Set(chosen.map(p=>p.category)).size>1?'서로 다른 보험 종류가 포함되어 있습니다. ':''}같은 나이·심사형·납기·통화인지 먼저 확인하세요. 환급률만으로 순위를 매기지 않습니다.</p><div class="product-comparison-scroll" tabindex="0" role="region" aria-label="선택 상품 비교표"><table class="product-comparison-table"><thead><tr><th scope="col">비교 항목</th>${chosen.map(p=>`<th scope="col"><span>${esc(p.insurer)} · ${esc(p.category)}</span>${esc(p.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(([label,key])=>`<tr><th scope="row">${label}</th>${cells(key)}</tr>`).join('')}</tbody></table></div>`;
    $('product-comparison').showModal();
  }
  async function load(){
    if(data)return;
    if(loading)return loading;
    loading=(async()=>{
      const r=await fetch('data/products.json',{cache:'no-cache'});if(!r.ok)throw new Error('HTTP '+r.status);
      const value=await r.json();if(value.schema_version!==1||!Array.isArray(value.products))throw new Error('Invalid catalog');
      data=value;sources=new Map(data.sources.map(s=>[s.id,s]));state=M.readState(new URL(location.href).searchParams,data);
      $('product-insurer').replaceChildren(new Option('전체 보험사',''),...data.insurers.map(s=>new Option(s,s)));
      $('product-pay').replaceChildren(new Option('전체 납입기간',''),...M.payOptions(data).map(p=>new Option(p.label,p.value)));
      $('product-insurer').value=state.insurer;$('product-pay').value=state.pay;$('product-query').value=state.query;$('product-previous').checked=state.previous;
      $('product-research-date').textContent='상품 자료정리일 '+data.research_date.replaceAll('-','.');
      $('product-scope').textContent=data.insurers.length+'개사 · '+data.products.length+'개 상품군';
      $('product-pending-summary').textContent='GA 취급·분류 추가 확인 '+data.pending.length+'개 상품';
      $('product-pending-list').innerHTML=data.pending.map(p=>`<li><strong>${esc(p.insurer)} · ${esc(p.name)}</strong><p>${esc(p.reason)}. ${esc(p.missing)}</p></li>`).join('');
      $('product-filters').hidden=false;
    })();
    try{await loading;}finally{loading=null;}
  }
  async function activate(){
    document.title='GA 상품비교 | 보험 영업 모닝브리프';
    try{await load();if(document.body.dataset.period==='products')render();}
    catch{$('product-list').innerHTML='<div class="product-empty"><h3>상품 자료를 불러오지 못했습니다.</h3><p>연결 상태를 확인한 뒤 다시 시도해주세요.</p><button type="button" data-retry>다시 불러오기</button></div>';}
  }
  window.addEventListener('brief:mode',e=>{if(e.detail.mode==='products')activate();else if($('product-comparison').open)$('product-comparison').close();});
  $('product-filters').addEventListener('submit',e=>e.preventDefault());
  for(const id of ['product-insurer','product-pay','product-previous'])$(id).addEventListener('change',changeFilters);
  $('product-query').addEventListener('input',changeFilters);
  $('product-categories').addEventListener('click',e=>{const b=e.target.closest('[data-category]');if(!b||!data)return;state.category=b.dataset.category;limit=12;render();});
  $('product-reset').addEventListener('click',reset);
  $('product-more').addEventListener('click',()=>{limit+=12;render();});
  $('product-list').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-retry'))activate();else if(b.hasAttribute('data-reset'))reset();else if(b.dataset.compare)toggleCompare(b.dataset.compare);});
  $('product-compare-selected').addEventListener('click',e=>{const b=e.target.closest('[data-remove]');if(b)toggleCompare(b.dataset.remove);});
  $('product-compare-open').addEventListener('click',openComparison);
  $('product-compare-clear').addEventListener('click',()=>{state.compare=[];render();});
  $('product-comparison-close').addEventListener('click',()=>$('product-comparison').close());
})();
