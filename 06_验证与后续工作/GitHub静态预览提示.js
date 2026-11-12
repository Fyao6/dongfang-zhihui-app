// GitHub Pages has no account/backend service. Keep the embedded APP unchanged.
(() => {
  'use strict';
  const frame = document.getElementById('experience-frame');
  const note = document.querySelector('.review-note');
  const scope = 'GitHub 在线交互预览：可查看界面、练习和本机排盘。账号、发布、创作者及管理后台需单独服务；个人资料仅保存在当前浏览器。';
  if (note) {
    note.textContent = scope;
    note.setAttribute('aria-live', 'polite');
  }
  const bound = new WeakSet();
  function bind() {
    const doc = frame?.contentDocument;
    if (!doc || bound.has(doc)) return;
    bound.add(doc);
    doc.addEventListener('click', event => {
      const link = event.target.closest?.('a[href]');
      if (!link) return;
      let url;
      try { url = new URL(link.getAttribute('href'), doc.baseURI); } catch { return; }
      if (url.origin !== location.origin || !/^\/(?:creator|admin|experience|api|app)(?:\/|$)/.test(url.pathname)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const message = '这是交互预览，账号、创作者及管理后台需要单独启动服务。';
      try {
        if (typeof frame.contentWindow.toast === 'function') frame.contentWindow.toast(message);
      } catch { /* The visible owner note below remains available. */ }
      if (note) note.textContent = message + ' ' + scope;
    }, true);
  }
  frame?.addEventListener('load', bind);
  bind();
  window.__EW_PAGES_PREVIEW__ = { backendConnected: false };
})();
