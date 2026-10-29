// Phone tab bar for the live app. It only appears on the app's own routes, so the static GitHub Pages build
// (which has no /today, /progress or /plan) never shows links that lead nowhere.
(function () {
  const TABS = [['Today', '/today', ''], ['Learn', '/learn', ''], ['Rep', '/today', '#rep'], ['Progress', '/progress', '']];
  const LIVE = ['/today', '/learn', '/progress', '/plan', '/home'];
  if (!LIVE.includes(location.pathname)) return;
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
    const flush = () => navigator.serviceWorker.ready.then(r => r.active && r.active.postMessage('replay')).catch(() => {});
    navigator.serviceWorker.addEventListener('message', e => { if (e.data && e.data.type === 'dp-sync') window.dispatchEvent(new CustomEvent('dp-sync', { detail: e.data })); });
    window.addEventListener('online', flush);
    flush();
  }
  const bar = document.createElement('nav');
  bar.className = 'tabbar';
  bar.setAttribute('aria-label', 'Main');
  function mark() {
    const here = location.pathname + (location.pathname === '/today' && location.hash === '#rep' ? '#rep' : '');
    bar.innerHTML = TABS.map(([name, path, hash]) =>
      `<a href="${path}${hash}"${path + hash === here ? ' class="on" aria-current="page"' : ''}>${name}</a>`).join('');
  }
  mark();
  window.addEventListener('hashchange', mark);
  document.body.appendChild(bar);
})();
