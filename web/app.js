'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = { latest:null, edition:null, archive:[], view:'card', archiveLimit:12, config:{}, status:{}, backfill:{} };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const allowedURL = url => { try { const u = new URL(url); return ['https:','http:'].includes(u.protocol) && !u.username && !u.password ? u.href : '#'; } catch { return '#'; } };
  const format = (date, options) => new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul',...options}).format(new Date(date));
  const dateOnly = date => date + 'T12:00:00+09:00';
  const pad = n => String(n).padStart(2,'0');
  let toastTimer;
  function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,4000); }
  async function getJSON(path) { const response=await fetch(path,{cache:'no-cache'}); if(!response.ok) throw new Error('HTTP '+response.status); return response.json(); }
  function currentArticles() { return state.edition.articles; }
  function card(article,index) {
    const d=format(article.published_at,{month:'2-digit',day:'2-digit'}).replace(/\.$/,'');
    const parts=article.summary_parts||{intro:article.title,body:article.summary,conclusion:article.implication||'발행 당시 상세 내용과 후속 전망은 원문에서 확인하세요.'};
    const rows=[['서론',parts.intro],['본론',parts.body],['결론',parts.conclusion]].map(([label,text])=>`<div class="summary-row"><span class="label">${label}</span><p>${esc(text)}</p></div>`).join('');
    return `<article class="news-card"><div class="rank">${pad(index+1)}</div><div><div class="card-meta"><span class="tag">${esc(article.category)}</span><span class="source">${esc(article.source)}</span><time datetime="${esc(article.published_at)}">${esc(d)}</time><a class="source-link" href="${esc(allowedURL(article.url))}" target="_blank" rel="noopener noreferrer">원문 보기</a></div><h4><a href="${esc(allowedURL(article.url))}" target="_blank" rel="noopener noreferrer">${esc(article.title)}</a></h4><div class="summary-parts">${rows}</div></div></article>`;
  }
  function render() {
    const edition=state.edition, items=currentArticles();
    document.body.classList.toggle('newspaper',state.view==='paper');
    $('view-card').setAttribute('aria-pressed',String(state.view==='card'));
    $('view-paper').setAttribute('aria-pressed',String(state.view==='paper'));
    $('articles').innerHTML=items.map(card).join('')||'<p class="empty">이 날짜에 수집처에서 확인한 선정 기준에 맞는 기사가 없습니다. 수집 결과는 아래 안내에서 확인할 수 있습니다.</p>';
    $('article-count').textContent=items.length+'건';
    $('paper-date').textContent=edition.date.replaceAll('-','.');
    $('paper-date').dateTime=edition.date;
    $('date-long').textContent=format(dateOnly(edition.date),{year:'numeric',month:'long',day:'numeric',weekday:'short'});
    $('updated-at').textContent=format(edition.updated_at,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})+' KST · '+(edition.mode==='ai'?'기사 발췌 기반 AI 요약':'기사 핵심 문장');
    $('mode-label').textContent='서론 · 본론 · 결론';
    $('edition-status').textContent=edition.backfilled?'BACKFILLED EDITION':edition===state.latest?'LATEST SELECTION':'FROM THE ARCHIVE';
    $('briefing-heading').textContent=edition===state.latest?'오늘의 주요 뉴스':edition.date.replaceAll('-','.')+' 브리프';
    $('paper').querySelector('h3').textContent=edition===state.latest?'오늘, 알아둘 이야기.':'그날, 알아둘 이야기.';
    $('page-label').textContent=items.length+'건 · 한 장에 모두 보기';
    const notices=[];
    if(edition.demo) notices.push('화면 미리보기용 예시입니다. 실제 뉴스 업데이트는 아직 시작되지 않았습니다.');
    if(edition.backfilled) {
      notices.push('소급 수집본 · '+edition.date+' 당일 발행 기사를 공개 목록에서 다시 수집했습니다. 과거 오전 8시 자동 실행 기록은 아닙니다.');
      if((edition.warnings||[]).length)notices.push(edition.warnings.join(' · '));
    }
    const age=(Date.now()-new Date(edition.updated_at).getTime())/3600000;
    if(edition===state.latest && !edition.demo && age>30) notices.push('현재 '+edition.date+' 최신 발행본을 보고 있습니다. 새 발행본이 등록되면 이 화면에 표시됩니다.');
    const checked=state.status.checked_at;
    if(edition===state.latest&&checked) {
      const checkLabel=format(checked,{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
      if(state.status.new_edition===false) notices.push('최근 수집 확인: '+checkLabel+' · 새로 선정된 기사 없이 기존 발행본을 유지했습니다.');
      if((state.status.warnings||[]).length) notices.push(state.status.warnings.join(' · '));
    }
    $('notice').hidden=!notices.length;
    $('notice').textContent=notices.join(' ');
    const coverage=edition.backfilled?edition.collection:state.status.collection;
    const configured=edition.backfilled?(coverage?.configured||[]):[...new Set((state.config.feeds||[]).map(f=>f.name))];
    const selected=[...new Set(items.map(a=>a.source))];
    $('source-coverage-heading').textContent='뉴스 수집처 '+configured.length+'곳 · 이번 발행 '+selected.length+'곳';
    $('source-configured').textContent=configured.join(' · ');
    $('source-succeeded').textContent=(coverage?.succeeded||[]).join(' · ')||'수집 성공 기록이 없습니다.';
    $('source-selected').textContent=selected.join(' · ');
    $('source-selected').textContent=selected.join(' · ')||'선정 기사 없음';
    document.querySelector('.source-policy').textContent=(edition.backfilled?'해당 날짜의 공개 기사 목록에서 발행일을 확인해 소급 수집했습니다.':'매체별 RSS 제공 범위에서 수집합니다.')+' 관련성·발행 시각·중복 여부를 비교하며 같은 매체는 최대 2건까지 선정합니다.';
    document.title=(state.config.title||'보험 영업 모닝브리프')+' · '+edition.date;
  }
  function renderArchive() {
    const query=$('archive-search').value.trim().toLowerCase();
    const rows=state.archive.filter(row=>(row.date+' '+row.title).toLowerCase().includes(query));
    const shown=rows.slice(0,state.archiveLimit);
    $('archive-list').innerHTML=shown.map(row=>`<button type="button" class="archive-row" data-date="${esc(row.date)}"><time datetime="${esc(row.date)}">${esc(row.date.replaceAll('-','.'))}</time><span class="archive-title">${esc(row.title)}</span><span class="archive-badge">${row.backfilled?'소급 수집':'발행본'} · ${Number(row.count)||0}건</span></button>`).join('')||`<p class="empty">${query?'검색 결과가 없습니다. 다른 날짜나 기사 제목으로 검색해보세요.':'첫 브리프부터 차곡차곡.<br>자동 발행된 뉴스가 날짜별로 이곳에 모입니다.'}</p>`;
    $('more-archive').hidden=shown.length>=rows.length;
    if(state.backfill.days?.length){$('backfill-note').hidden=false;$('backfill-note').textContent=state.backfill.start.replaceAll('-','.')+' ~ '+state.backfill.end.replaceAll('-','.')+' · '+state.backfill.days.length+'일 수집 확인. 소급 수집본은 당일 발행 기사로 재구성했으며, 과거 예약 실행 성공을 의미하지 않습니다.';}
  }
  async function openDate(date) {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
    if(date===state.latest.date) state.edition=state.latest;
    else {
      const record=state.archive.find(row=>row.date===date);
      if(!record) { toast('해당 날짜의 브리프가 없습니다.'); return; }
      // File path is derived from a validated date, not untrusted JSON.
      try { state.edition=await getJSON('data/editions/'+date+'.json'); }
      catch { toast('브리프를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.'); return; }
    }
    render();
    const url=new URL(location.href);url.searchParams.set('date',date);url.hash='briefing';
    history.replaceState(null,'',url);
    $('briefing').scrollIntoView({behavior:'smooth'});
  }
  function view(mode) { state.view=mode;try{localStorage.setItem('brief-view',mode);}catch{}render(); }
  $('view-card').addEventListener('click',()=>view('card'));
  $('view-paper').addEventListener('click',()=>view('paper'));
  $('archive-search').addEventListener('input',()=>{state.archiveLimit=12;renderArchive();});
  $('more-archive').addEventListener('click',()=>{state.archiveLimit+=12;renderArchive();});
  $('archive-list').addEventListener('click',e=>{const row=e.target.closest('[data-date]');if(row)openDate(row.dataset.date);});
  $('share').addEventListener('click',async()=>{
    if(!state.edition)return;
    const url=new URL(location.href);url.searchParams.set('date',state.edition.date);url.hash='';
    try { if(navigator.share) await navigator.share({title:document.title,url:url.href});else {await navigator.clipboard.writeText(url.href);toast('브리프 링크를 복사했습니다. 카카오톡 등에 붙여넣어 공유하세요.');} }
    catch(error){if(error.name!=='AbortError')toast('주소창의 링크를 복사해 공유해주세요.');}
  });
  $('print').addEventListener('click',()=>window.print());
  async function init() {
    try {
      const bootstrap=window.BRIEFING_BOOTSTRAP;
      const values=bootstrap||{config:await getJSON('config.json'),latest:await getJSON('data/latest.json'),archive:await getJSON('data/archive.json'),status:await getJSON('data/status.json').catch(()=>({})),backfill:await getJSON('data/backfill-report.json').catch(()=>({}))};
      state.config=values.config;state.latest=values.latest;state.edition=state.latest;state.archive=values.archive;state.status=values.status||{};state.backfill=values.backfill||{};
      try{state.view=localStorage.getItem('brief-view')==='paper'?'paper':'card';}catch{}
      $('site-title').textContent=state.config.title;
      // Preserve a deliberate two-line masthead without injecting configuration as HTML.
      const h=$('site-title');if(state.config.title.startsWith('보험 영업 '))h.replaceChildren(document.createTextNode('보험 영업'),document.createElement('br'),Object.assign(document.createElement('span'),{textContent:state.config.title.replace(/^보험 영업\s*/, '')}));
      $('subtitle').textContent=state.config.subtitle;
      $('edition-label').textContent=state.config.edition_label;
      render();renderArchive();
      const date=new URL(location.href).searchParams.get('date');if(date&&date!==state.latest.date)await openDate(date);
    } catch { $('articles').innerHTML='<p class="empty">뉴스를 불러오지 못했습니다. 새로고침 후 다시 확인해주세요.</p>'; }
  }
  init();
})();
