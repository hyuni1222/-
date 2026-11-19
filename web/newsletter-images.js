'use strict';
(()=>{
  const panel=document.getElementById('products-panel');
  const viewer=document.getElementById('newsletter-viewer');
  const body=document.getElementById('newsletter-viewer-body');
  panel.addEventListener('click',event=>{
    const button=event.target.closest('[data-newsletter-image]');
    if(!button)return;
    const frame=button.querySelector('.newsletter-image-frame').cloneNode(true);
    frame.querySelector('img').loading='eager';
    document.getElementById('newsletter-viewer-title').textContent=button.getAttribute('aria-label').replace(' 크게 보기','');
    body.replaceChildren(frame);
    viewer.showModal();
  });
  document.getElementById('newsletter-viewer-close').addEventListener('click',()=>viewer.close());
  viewer.addEventListener('click',event=>{if(event.target===viewer)viewer.close();});
  window.addEventListener('brief:mode',event=>{if(event.detail.mode!=='products'&&viewer.open)viewer.close();});
})();
