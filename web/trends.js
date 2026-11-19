'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL=value=>{try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'#';}catch{return '#';}};
  const state={mode:'daily',index:null,period:null,limit:20,request:0};
  const labels={daily:'일일 브리프',weekly:'주간동향',monthly:'월간동향',products:'보험사별 소식지'};
  const cache=new Map();
  async function json(path){const r=await fetch(path,{cache:'no-cache'});if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
  const range=period=>period.start.replaceAll('-','.')+' — '+period.end.replaceAll('-','.');
  function rows(parts,insight=false){return [['서론',parts.intro],['본론',parts.body],['결론',parts.conclusion]].map(([label,text])=>`<div class="summary-row"><span class="label">${label}</span><p>${escape(text)}${insight&&label==='결론'?'<small class="interpretation">보험영업 관점의 해석</small>':''}</p></div>`).join('');}
  function refs(evidence){return `<details class="trend-evidence"><summary>근거 기사 ${evidence.length}건</summary>${evidence.map(a=>`<a href="${escape(safeURL(a.url))}" target="_blank" rel="noopener noreferrer"><span>${escape(a.published_at.slice(5,10).replace('-','.'))} · ${escape(a.source)}</span>${escape(a.title)}</a>`).join('')}</details>`;}
  function reportHTML(period){
    const report=period.report;
    const references=report.references||[];
    const byId=new Map(references.map((r,i)=>[r.id,{...r,number:i+1}]));
    const citations=ids=>(ids||[]).map(id=>byId.get(id)).filter(Boolean).map(r=>`<a class="report-citation" href="${escape(safeURL(r.url))}" target="_blank" rel="noopener noreferrer" aria-label="근거 ${r.number}: ${escape(r.title)}">[${r.number}]</a>`).join(' ');
    const paragraphs=items=>(items||[]).map(p=>`<p>${escape(p.text)} <span class="report-citations">${citations(p.source_ids)}</span></p>`).join('');
    const executive=`<section class="report-executive"><p class="report-kicker">EXECUTIVE SUMMARY</p><h4>핵심 요약</h4>${paragraphs(report.executive_summary)}${report.continuity?.length?`<p class="report-continuity"><strong>이전 기간과 이어지는 쟁점</strong> ${escape(report.continuity.join(' · '))}</p>`:''}</section>`;
    const timeline=report.timeline?.length?`<section class="report-timeline-section"><h4>월간 전개 흐름</h4><ol class="report-timeline">${report.timeline.map(p=>`<li><time>${escape(p.start.slice(5).replace('-','.'))} ~ ${escape(p.end.slice(5).replace('-','.'))}</time><div><strong>${escape(p.title)}</strong><p>${escape(p.text)} ${citations(p.source_ids)}</p></div></li>`).join('')}</ol></section>`:'';
    const sections=report.sections.map(section=>`<section class="report-category"><header><h4>${escape(section.title)}</h4><span>${section.article_count}건 검토</span></header><p class="report-angle">${escape(section.angle)}</p><h5>주요 동향</h5>${paragraphs(section.developments)}<div class="report-interpretation"><h5>영업적 의미</h5>${paragraphs(section.interpretation)}</div>${section.actions.length?`<div class="report-task"><h5>대응 과제</h5><p>${escape(section.actions[0].task)} ${citations(section.actions[0].source_ids)}</p><p class="report-metrics"><strong>확인 지표</strong> ${escape(section.actions[0].metrics.join(' · '))}</p></div>`:''}</section>`).join('');
    const management=`<section class="report-management"><h4>종합 시사점</h4>${report.management.map(p=>`<h5>${escape(p.title)}</h5><p>${escape(p.text)} ${citations(p.source_ids)}</p>`).join('')}</section>`;
    const agenda=`<section class="report-agenda"><h4>${state.mode==='weekly'?'다음 업무 점검표':'다음 기간 관리 과제'}</h4><div class="report-table-wrap"><table><thead><tr><th scope="col">쟁점·담당</th><th scope="col">실행·후속 확인</th><th scope="col">관리 지표</th></tr></thead><tbody>${report.agenda.map(a=>`<tr><th scope="row">${escape(a.issue)}<small>${escape(a.owner)}</small></th><td><p>${escape(a.task)}</p><small>후속 확인: ${escape(a.watch)}</small></td><td>${escape(a.metrics.join(' · '))}</td></tr>`).join('')}</tbody></table></div></section>`;
    const referenceList=`<details class="report-references"><summary>분석 근거 ${references.length}건</summary><ol>${references.map(r=>`<li><a href="${escape(safeURL(r.url))}" target="_blank" rel="noopener noreferrer"><span>${escape(r.published_at.slice(0,10))} · ${escape(r.source)}</span>${escape(r.title)}</a></li>`).join('')}</ol></details>`;
    return executive+timeline+sections+management+agenda+referenceList;
  }
  function render(period){
    state.period=period;state.limit=20;$('trend-search').value='';
    const status=period.in_progress?'오늘까지 집계':period.partial?'10월 1일부터 집계':'기간 전체 집계';
    const coverage=period.coverage_days+'/'+period.expected_days+'일 수집 확인';
    $('trend-content').innerHTML=`<article class="trend-paper"><header class="trend-paper-header"><span>${state.mode==='weekly'?'WEEKLY':'MONTHLY'} INSURANCE REPORT</span><span>${escape(status)}</span></header><p class="trend-range">${escape(range(period))}</p><h3>${escape(period.report?.title||(state.mode==='weekly'?'보험영업 주간 리포트':'보험영업 월간 리포트'))}</h3><div class="trend-stats"><span><b>${period.article_count}</b> 검토 기사</span><span><b>${period.source_count}</b> 매체</span><span><b>${period.themes.length}</b> 분석 분야</span></div><div class="report-body">${period.report?reportHTML(period):'<p class="empty">리포트를 준비하고 있습니다.</p>'}</div><footer class="trend-paper-footer"><span>${escape(coverage)}</span><span>기사 근거 · 영업 해석 · 대응 과제</span></footer></article>${period.warning_days.length?'<p class="trend-coverage-note">일부 날짜는 수집처 연결에 제한이 있어 확인된 기사 범위로 정리했습니다.</p>':''}`;
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
    document.querySelector('.skip').href=mode==='daily'?'#briefing':mode==='products'?'#products-panel':'#trends-panel';
    document.querySelectorAll('[role="tab"][data-period]').forEach(tab=>{const selected=tab.dataset.period===mode;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;});
    $('daily-panel').hidden=mode!=='daily';$('trends-panel').hidden=!['weekly','monthly'].includes(mode);$('products-panel').hidden=mode!=='products';
    window.dispatchEvent(new CustomEvent('brief:mode',{detail:{mode}}));
    if(mode==='products'){
      document.title=labels.products+' | 보험 영업 모닝브리프';
      const url=new URL(location.href);url.searchParams.set('view','products');
      for(const key of ['period','date','insurer','category','pay','q','previous','compare'])url.searchParams.delete(key);
      url.hash='';history.replaceState(null,'',url);return;
    }
    {const url=new URL(location.href);for(const key of ['insurer','category','pay','q','previous','compare'])url.searchParams.delete(key);history.replaceState(null,'',url);}
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
  if(['weekly','monthly','products'].includes(initial))setMode(initial,params.get('period'));
})();
