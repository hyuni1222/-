'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = { latest:null, edition:null, archive:[], view:'card', page:0, archiveLimit:8, config:{}, status:{} };
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
    return `<article class="news-card"><div class="rank">${pad(index+1)}</div><div><div class="card-meta"><span class="tag">${esc(article.category)}</span><span class="source">${esc(article.source)}</span><time datetime="${esc(article.published_at)}">${esc(d)}</time></div><h4><a href="${esc(allowedURL(article.url))}" target="_blank" rel="noopener noreferrer">${esc(article.title)}</a></h4><div class="summary-row"><span class="label">${article.summary_kind==='ai'?'핵심':'발췌'}</span><p>${esc(article.summary)}</p></div>${article.implication?`<div class="summary-row insight"><span class="label">체크</span><p>${esc(article.implication)}</p></div>`:''}<a class="source-link" href="${esc(allowedURL(article.url))}" target="_blank" rel="noopener noreferrer">기사 원문 읽기 <span aria-hidden="true">↗</span></a></div></article>`;
  }
  function render() {
    const edition=state.edition, items=currentArticles(), pages=Math.ceil(items.length/3)||1;
    state.page=Math.max(0,Math.min(state.page,pages-1));
    const visible=state.view==='paper'?items:items.slice(state.page*3,state.page*3+3);
    document.body.classList.toggle('newspaper',state.view==='paper');
    $('view-card').setAttribute('aria-pressed',String(state.view==='card'));
    $('view-paper').setAttribute('aria-pressed',String(state.view==='paper'));
    $('articles').innerHTML=visible.map((a,i)=>card(a,state.view==='paper'?i:state.page*3+i)).join('')||'<p class="empty">아직 선정된 뉴스가 없습니다.</p>';
    $('article-count').textContent=items.length+'건';
    $('paper-date').textContent=edition.date.replaceAll('-','.');
    $('paper-date').dateTime=edition.date;
    $('date-long').textContent=format(dateOnly(edition.date),{year:'numeric',month:'long',day:'numeric',weekday:'short'});
    $('updated-at').textContent=format(edition.updated_at,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})+' KST · '+(edition.mode==='ai'?'RSS 기반 AI 요약':'RSS 발췌');
    $('mode-label').textContent=edition.mode==='ai'?'RSS 기반 AI 요약 · 체크 질문':'RSS 발췌 · 원문 확인';
    $('edition-status').textContent=edition===state.latest?'LATEST SELECTION':'FROM THE ARCHIVE';
    $('page-label').textContent=state.view==='paper'?pad(items.length)+' ARTICLES':pad(state.page+1)+' / '+pad(pages);
    $('pager').hidden=state.view==='paper'||pages<2;
    $('prev').disabled=state.page===0;
    $('next').disabled=state.page===pages-1;
    $('dots').innerHTML=Array.from({length:pages},(_,i)=>`<button type="button" aria-label="${i+1}번째 장" aria-current="${i===state.page}" data-page="${i}"></button>`).join('');
    const notices=[];
    if(edition.demo) notices.push('화면 미리보기용 예시입니다. 실제 뉴스 업데이트는 아직 시작되지 않았습니다.');
    const age=(Date.now()-new Date(edition.updated_at).getTime())/3600000;
    if(!edition.demo && age>30) notices.push('현재 '+edition.date+' 최신 발행본을 보고 있습니다. 새 발행본이 등록되면 이 화면에 표시됩니다.');
    const checked=state.status.checked_at;
    if(edition===state.latest&&checked) {
      const checkLabel=format(checked,{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
      if(state.status.new_edition===false) notices.push('최근 수집 확인: '+checkLabel+' · 새로 선정된 기사 없이 기존 발행본을 유지했습니다.');
      if((state.status.warnings||[]).length) notices.push(state.status.warnings.join(' · '));
    }
    $('notice').hidden=!notices.length;
    $('notice').textContent=notices.join(' ');
    document.title=(state.config.title||'보험 영업 모닝브리프')+' · '+edition.date;
  }
  function renderArchive() {
    const query=$('archive-search').value.trim().toLowerCase();
    const rows=state.archive.filter(row=>(row.date+' '+row.title).toLowerCase().includes(query));
    const shown=rows.slice(0,state.archiveLimit);
    $('archive-list').innerHTML=shown.map(row=>`<button type="button" class="archive-row" data-date="${esc(row.date)}"><time datetime="${esc(row.date)}">${esc(row.date.replaceAll('-','.'))}</time><span class="archive-title">${esc(row.title)}</span><span class="arrow" aria-hidden="true">↗</span></button>`).join('')||`<p class="empty">${query?'검색 결과가 없습니다. 다른 날짜나 기사 제목으로 검색해보세요.':'첫 브리프부터 차곡차곡.<br>자동 발행된 뉴스가 날짜별로 이곳에 모입니다.'}</p>`;
    $('more-archive').hidden=shown.length>=rows.length;
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
    state.page=0;render();
    const url=new URL(location.href);url.searchParams.set('date',date);url.hash='briefing';
    history.replaceState(null,'',url);
    $('briefing').scrollIntoView({behavior:'smooth'});
  }
  function view(mode) { state.view=mode;state.page=0;try{localStorage.setItem('brief-view',mode);}catch{}render(); }
  $('view-card').addEventListener('click',()=>view('card'));
  $('view-paper').addEventListener('click',()=>view('paper'));
  $('prev').addEventListener('click',()=>{state.page--;render();});
  $('next').addEventListener('click',()=>{state.page++;render();});
  $('dots').addEventListener('click',e=>{const button=e.target.closest('[data-page]');if(button){state.page=Number(button.dataset.page);render();}});
  $('archive-search').addEventListener('input',()=>{state.archiveLimit=8;renderArchive();});
  $('more-archive').addEventListener('click',()=>{state.archiveLimit+=8;renderArchive();});
  $('archive-list').addEventListener('click',e=>{const row=e.target.closest('[data-date]');if(row)openDate(row.dataset.date);});
  let touchStart;
  $('paper').addEventListener('touchstart',e=>{const t=e.changedTouches[0];touchStart={x:t.clientX,y:t.clientY};},{passive:true});
  $('paper').addEventListener('touchend',e=>{if(!touchStart||state.view!=='card')return;const t=e.changedTouches[0],dx=t.clientX-touchStart.x,dy=t.clientY-touchStart.y;touchStart=null;if(Math.abs(dx)>65&&Math.abs(dx)>Math.abs(dy)*1.5){state.page+=dx<0?1:-1;render();}},{passive:true});
  $('share').addEventListener('click',async()=>{
    if(!state.edition)return;
    const url=new URL(location.href);url.searchParams.set('date',state.edition.date);url.hash='';
    try { if(navigator.share) await navigator.share({title:document.title,url:url.href});else {await navigator.clipboard.writeText(url.href);toast('브리프 링크를 복사했습니다. 카카오톡 등에 붙여넣어 공유하세요.');} }
    catch(error){if(error.name!=='AbortError')toast('주소창의 링크를 복사해 공유해주세요.');}
  });
  let printView;
  window.addEventListener('beforeprint',()=>{if(state.edition){printView=state.view;state.view='paper';render();}});
  window.addEventListener('afterprint',()=>{if(printView){state.view=printView;printView=null;render();}});
  $('print').addEventListener('click',()=>window.print());
  async function init() {
    try {
      const bootstrap=window.BRIEFING_BOOTSTRAP;
      const values=bootstrap||{config:await getJSON('config.json'),latest:await getJSON('data/latest.json'),archive:await getJSON('data/archive.json'),status:await getJSON('data/status.json').catch(()=>({}))};
      state.config=values.config;state.latest=values.latest;state.edition=state.latest;state.archive=values.archive;state.status=values.status||{};
      try{state.view=localStorage.getItem('brief-view')==='paper'?'paper':'card';}catch{}
      $('site-title').textContent=state.config.title;
      // Preserve a deliberate two-line masthead without injecting configuration as HTML.
      const h=$('site-title');if(state.config.title.startsWith('보험 영업 '))h.replaceChildren(document.createTextNode('보험 영업'),document.createElement('br'),Object.assign(document.createElement('span'),{textContent:state.config.title.replace(/^보험 영업\s*/, '')+'.'}));
      $('subtitle').textContent=state.config.subtitle;
      $('edition-label').textContent=state.config.edition_label;
      render();renderArchive();
      const date=new URL(location.href).searchParams.get('date');if(date&&date!==state.latest.date)await openDate(date);
    } catch { $('articles').innerHTML='<p class="empty">뉴스를 불러오지 못했습니다. 새로고침 후 다시 확인해주세요.</p>'; }
  }
  init();
})();
