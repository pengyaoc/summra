// The installed app uses the same authenticated pages and reading progress.
(() => {
    const root = (window.APP_BASE_PATH || '').replace(/\/$/, '') + '/';
    if ('serviceWorker' in navigator && window.isSecureContext) {
        const register = () => {
            navigator.serviceWorker.register(root + 'sw.js', {
                scope: root, updateViaCache: 'none',
            }).catch(error => console.warn('Distill app registration failed:', error));
        };
        if (document.readyState === 'complete') register();
        else window.addEventListener('load', register, {once:true});
    }

    const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    const guide = document.getElementById('distill-ios-install');
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    let dismissed = false;
    try { dismissed = localStorage.getItem('distill-install-dismissed') === '1'; } catch (_) {}
    if (guide && ios && !standalone() && !dismissed && !document.body.classList.contains('on-reader-page')) guide.hidden = false;
    guide?.querySelector('button')?.addEventListener('click', () => {
        guide.hidden = true;
        try { localStorage.setItem('distill-install-dismissed', '1'); } catch (_) {}
    });
    window.addEventListener('appinstalled', () => {
        if (guide) guide.hidden = true;
    });
})();
