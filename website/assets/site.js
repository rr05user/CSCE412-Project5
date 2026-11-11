(()=>{
  const root = document.documentElement;
  try { const saved=localStorage.getItem('csce412-theme'); if(saved==='light'||saved==='dark') root.dataset.theme=saved; } catch(e) {}
  const theme=document.getElementById('theme-toggle');
  if(theme) theme.addEventListener('click',()=>{
    root.dataset.theme=root.dataset.theme==='light'?'dark':'light';
    try {localStorage.setItem('csce412-theme',root.dataset.theme)} catch(e) {}
  });
  const menu=document.getElementById('menu-toggle'), nav=document.getElementById('main-nav');
  if(menu&&nav) menu.addEventListener('click',()=>{
    const open=nav.classList.toggle('is-open'); menu.setAttribute('aria-expanded',String(open));
  });
})();
