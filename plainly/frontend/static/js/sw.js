// Network-only: no cached HTML, stale CSS/JS, personal reading state, or books.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
    if (event.request.mode !== 'navigate' || !event.request.url.startsWith(self.registration.scope)) return;
    event.respondWith(fetch(event.request).catch(() => new Response(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#8A2E2E"><title>Offline · Plainly</title>
<style>body{background:#F6F1E7;color:#302b26;font:18px/1.6 system-ui;margin:15vh auto;padding:24px;max-width:460px}h1{font-family:Georgia,serif}a{color:#8A2E2E}</style></head>
<body><h1>Plainly</h1><h2>You’re offline</h2><p>Reconnect to open your books and continue reading.</p>
<p><a href="${self.registration.scope}">Try again</a></p></body></html>`, {
        status: 503, headers: {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'},
    })));
});
