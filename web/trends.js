'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL=value=>{try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'#';}catch{return '#';}};
  const state={mode:'daily',index:null,period:null,limit:20,request:0};
  const labels={daily:'일일 브리프',weekly:'주간동향',monthly:'월간동향'};
  const cache=new Map();
  async function json(path){const r=await fetch(path,{cache:'no-cache'});if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
  const range=period=>period.start.replaceAll('-','.')+' — '+period.end.replaceAll('-','.');
  function rows(parts,insight=false){return [['서론',parts.intro],['본론',parts.body],['결론',parts.conclusion]].map(([label,text])=>`<div class="summary-row"><span class="label">${label}</span><p>${escape(text)}${insight&&label==='결론'?'<small class="interpretation">보험영업 관점의 해석</small>':''}</p></div>`).join('');}
  function refs(evidence){return `<details class="trend-evidence"><summary>근거 기사 ${evidence.length}건</summary>${evidence.map(a=>`<a href="${escape(safeURL(a.url))}" target="_blank" rel="noopener noreferrer"><span>${escape(a.published_at.slice(5,10).replace('-','.'))} · ${escape(a.source)}</span>${escape(a.title)}</a>`).join('')}</details>`;}
  function render(period){
    state.period=period;state.limit=20;$('trend-search').value='';
    const status=period.in_progress?'오늘까지 집계':period.partial?'10월 1일부터 집계':'기간 전체 집계';
    const coverage=period.coverage_days+'/'+period.expected_days+'일 수집 확인';
    $('trend-content').innerHTML=`<article class="trend-paper"><header class="trend-paper-header"><span>${state.mode==='weekly'?'WEEKLY':'MONTHLY'} INSURANCE BRIEF</span><span>${escape(status)}</span></header><p class="trend-range">${escape(range(period))}</p><h3>${state.mode==='weekly'?'한 주의 흐름을 읽다':'한 달의 흐름을 읽다'}</h3><div class="trend-stats"><span><b>${period.article_count}</b> 분석 기사</span><span><b>${period.source_count}</b> 매체</span><span><b>${period.themes.length}</b> 주요 주제</span></div><div class="trend-overview"><p class="trend-section-label">기간 요약</p>${rows(period.summary_parts)}</div>${period.themes.map(theme=>`<section class="trend-theme"><div class="trend-theme-title"><h4>${escape(theme.title)}</h4><span>${theme.count}건</span></div>${rows(theme.summary_parts,true)}${refs(theme.evidence)}</section>`).join('')||'<p class="empty">이 기간의 관련 기사를 확인하지 못했습니다.</p>'}<footer class="trend-paper-footer"><span>${escape(coverage)}</span><span>서론 · 본론 · 결론</span></footer></article>${period.warning_days.length?'<p class="trend-coverage-note">일부 날짜는 수집처 연결에 제한이 있어 확인된 기사 범위로 정리했습니다.</p>':''}`;
    $('trend-library-count').textContent=period.article_count+'건';$('trend-library').hidden=false;
    $('trend-method').textContent='전체 수집 기간 '+state.index.collection_start.replaceAll('-','.')+' ~ '+state.index.collection_end.replaceAll('-','.')+' · 저장 '+state.index.stored_articles+'건 / 분석 '+state.index.article_count+'건. '+state.index.method;
    document.title=labels[state.mode]+' · '+period.label+' | 보험 영업 모닝브리프';
    renderArticles();
  }
  function renderArticles(){
    if(!state.period)return;
    const query=$('trend-search').value.trim().toLowerCase();
    const items=state.period.articles.filter(a=>(a.title+' '+a.source+' '+a.published_at.slice(0,10)).toLowerCase().includes(query));
    $('trend-article-list').innerHTML=items.slice(0,state.limit).map(a=>`<a class="trend-article" href="${escape(safeURL(a.url))}" target="_blank" rel="noopener noreferrer"><time datetime="${escape(a.published_at)}">${escape(a.published_at.slice(0,10).replaceAll('-','.'))}</time><span>${escape(a.title)}</span><small>${escape(a.source)}</small></a>`).join('')||'<p class="empty">검색 결과가 없습니다.</p>';
    $('trend-more').hidden=items.length<=state.limit;
  }
  async function openPeriod(id){
    const request=++state.request,mode=state.mode;
    const entry=state.index?.[mode]?.find(p=>p.id===id)||state.index?.[mode]?.[0];
    if(!entry){$('trend-content').innerHTML='<p class="empty">아직 이 기간의 동향이 없습니다.</p>';return;}
    $('trend-period').value=entry.id;$('trend-library').hidden=true;
    $('trend-content').innerHTML='<p class="empty">기간별 동향을 불러오고 있습니다.</p>';
    const url=new URL(location.href);url.searchParams.set('view',mode);url.searchParams.set('period',entry.id);url.searchParams.delete('date');url.hash='';history.replaceState(null,'',url);
    // Paths and IDs are derived from the supported period format, not arbitrary URLs.
    if(!/^(\d{4}-\d{2}-\d{2}|\d{4}-\d{2})$/.test(entry.id))return;
    const path='data/trends/'+mode+'/'+entry.id+'.json';
    try{if(!cache.has(path))cache.set(path,await json(path));if(request===state.request&&mode===state.mode)render(cache.get(path));}
    catch{if(request===state.request)$('trend-content').innerHTML='<p class="empty">동향을 불러오지 못했습니다. 기간을 다시 선택해주세요.</p>';}
  }
  async function setMode(mode,id){
    if(!Object.hasOwn(labels,mode))return;
    state.mode=mode;++state.request;document.body.dataset.period=mode;
    document.querySelector('.skip').href=mode==='daily'?'#briefing':'#trends-panel';
    document.querySelectorAll('[role="tab"][data-period]').forEach(tab=>{const selected=tab.dataset.period===mode;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;});
    $('daily-panel').hidden=mode!=='daily';$('trends-panel').hidden=mode==='daily';
    if(mode==='daily'){
      const url=new URL(location.href);url.searchParams.delete('view');url.searchParams.delete('period');history.replaceState(null,'',url);
      document.title='보험 영업 모닝브리프 · '+$('paper-date').dateTime;return;
    }
    $('trends-panel').setAttribute('aria-labelledby','tab-'+mode);
    $('trend-heading').textContent=labels[mode];$('trend-eyebrow').textContent=mode==='weekly'?'WEEKLY TRENDS':'MONTHLY TRENDS';
    try{
      if(!state.index)state.index=window.BRIEFING_BOOTSTRAP?.trends||await json('data/trends.json');
      if(state.mode!==mode)return;
      $('trend-period').replaceChildren(...(state.index[mode]||[]).map(p=>Object.assign(document.createElement('option'),{value:p.id,textContent:p.label+(p.in_progress?' · 진행 중':'')})));
      await openPeriod(id);
    }catch{$('trend-content').innerHTML='<p class="empty">동향 데이터를 불러오지 못했습니다. 새로고침 후 확인해주세요.</p>';}
  }
  const tabs=[...document.querySelectorAll('[role="tab"][data-period]')];
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>setMode(tab.dataset.period));
    tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();tabs[next].focus();setMode(tabs[next].dataset.period);}});
  });
  document.querySelectorAll('[data-view-link]').forEach(link=>link.addEventListener('click',()=>setMode('daily')));
  $('trend-period').addEventListener('change',()=>openPeriod($('trend-period').value));
  $('trend-search').addEventListener('input',()=>{state.limit=20;renderArticles();});
  $('trend-more').addEventListener('click',()=>{state.limit+=20;renderArticles();});
  $('trend-print').addEventListener('click',()=>window.print());
  const params=new URL(location.href).searchParams,initial=params.get('view');
  if(['weekly','monthly'].includes(initial))setMode(initial,params.get('period'));
})();
