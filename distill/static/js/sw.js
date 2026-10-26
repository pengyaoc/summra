// Network-only: never persist private books, pages, or progress in Cache Storage.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
    if (event.request.mode !== 'navigate') return;
    const url = new URL(event.request.url);
    if (!url.href.startsWith(self.registration.scope)) return;
    event.respondWith(fetch(event.request).catch(() => new Response(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#8A2E2E"><title>Offline · Distill</title>
<style>body{background:#FBF8F1;color:#302b26;font:18px/1.6 system-ui;margin:15vh auto;padding:24px;max-width:460px}h1{font-family:Georgia,serif}a{color:#8A2E2E}</style></head>
<body><h1>Distill</h1><h2>You’re offline</h2><p>Reconnect to open your library and continue reading.</p>
<p><a href="${self.registration.scope}">Try again</a></p></body></html>`, {
        status: 503, headers: {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'},
    })));
});
