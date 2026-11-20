'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL=value=>{try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'#';}catch{return '#';}};
  const insurers=[...document.querySelectorAll('.insurer-news')];
  const navigate=mode=>window.dispatchEvent(new CustomEvent('brief:navigate',{detail:{mode}}));
  function filterNewsletters(){
    const query=$('newsletter-search').value.trim().toLocaleLowerCase('ko-KR');
    let count=0;
    for(const card of insurers){const matches=card.querySelector('h3').textContent.toLocaleLowerCase('ko-KR').includes(query)||card.querySelector('ul').textContent.toLocaleLowerCase('ko-KR').includes(query);card.hidden=!matches;if(matches)count++;}
    $('newsletter-count').textContent=(query?'검색 결과 ':'전체 ')+count+'개사';
    $('newsletter-empty').hidden=count!==0;$('newsletter-reset').hidden=!query;
  }
  $('newsletter-search').addEventListener('input',filterNewsletters);
  $('newsletter-reset').addEventListener('click',()=>{$('newsletter-search').value='';filterNewsletters();$('newsletter-search').focus();});
  document.addEventListener('click',event=>{
    const control=event.target.closest('[data-open-view]');if(!control)return;
    event.preventDefault();navigate(control.dataset.openView);
    if(control.hasAttribute('data-latest'))window.dispatchEvent(new Event('brief:latest'));
    if(control.dataset.insurer){$('newsletter-search').value=control.dataset.insurer;filterNewsletters();}
    else if(control.dataset.openView==='products'){$('newsletter-search').value='';filterNewsletters();}
    const target=control.dataset.scroll?$(control.dataset.scroll):$('portal-main');
    target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
  });
  window.addEventListener('brief:mode',event=>{
    document.querySelectorAll('[data-open-view="home"]').forEach(a=>{if(event.detail.mode==='home')a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  });
  function render(values){
    const latest=values.latest,items=latest.articles||[];
    const date=latest.date.replaceAll('-','.');
    $('mini-date').textContent=date;
    $('home-edition-date').textContent=date;
    $('home-news-count').textContent=items.length;
    $('home-insurer-count').textContent=insurers.length;
    $('home-news').innerHTML=items.slice(0,3).map((a,i)=>`<article class="home-news-item"><span class="home-news-rank" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><div><div class="home-news-meta"><span class="home-category">${escape(a.category)}</span><span>${escape(a.source)}</span><time datetime="${escape(a.published_at)}">${escape(new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit'}).format(new Date(a.published_at)).replace(/\.$/,''))}</time></div><h3><a href="${escape(safeURL(a.url))}" target="_blank" rel="noopener noreferrer">${escape(a.title)}</a></h3><p>${escape(values.daily_analysis?.[a.id]?.summary||a.summary||a.summary_parts?.body||'원문에서 자세한 내용을 확인하세요.')}</p></div></article>`).join('')||'<p class="empty">아직 발행된 뉴스가 없습니다.</p>';
    $('mini-stories').innerHTML=items.slice(0,3).map(a=>`<span class="mini-story"><small>${escape(a.category)}</small><span>${escape(a.title)}</span></span>`).join('');
    const sourceDate=new Date(latest.updated_at);
    if(!Number.isNaN(sourceDate.getTime()))$('portal-last-updated').textContent='최근 발행 '+new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(sourceDate);
    const weekly=values.trends?.weekly?.[0],monthly=values.trends?.monthly?.[0];
    if(weekly)$('home-weekly-period').textContent=weekly.label;
    if(monthly)$('home-monthly-period').textContent=monthly.label;
  }
  $('home-insurers').replaceChildren(...insurers.slice(0,6).map(card=>{
    const name=card.querySelector('h3').textContent,button=document.createElement('button');
    button.type='button';button.dataset.openView='products';button.dataset.insurer=name;button.textContent=name;return button;
  }));
  filterNewsletters();
  if(window.BRIEFING_BOOTSTRAP)render(window.BRIEFING_BOOTSTRAP);
  else Promise.all(['latest','trends'].map(name=>fetch('data/'+name+'.json').then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}))).then(([latest,trends])=>render({latest,trends})).catch(()=>{$('home-news').innerHTML='<p class="empty">최신 뉴스를 불러오지 못했습니다. 새로고침 후 확인해주세요.</p>';$('mini-date').textContent='발행본을 불러오지 못했습니다.';});
})();
