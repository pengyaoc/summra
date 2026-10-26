// The installed app uses the same authenticated pages and reading progress.
(() => {
    const root = (window.APP_BASE_PATH || '').replace(/\/$/, '') + '/';
    if ('serviceWorker' in navigator && window.isSecureContext) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register(root + 'sw.js', {
                scope: root, updateViaCache: 'none',
            }).catch(error => console.warn('Distill app registration failed:', error));
        });
    }

    const button = document.getElementById('distill-install-button');
    let installPrompt;
    const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    window.addEventListener('beforeinstallprompt', event => {
        if (!button || standalone()) return;
        event.preventDefault();
        installPrompt = event;
        button.hidden = false;
    });
    button?.addEventListener('click', async () => {
        if (!installPrompt) return;
        const prompt = installPrompt;
        installPrompt = null;
        button.hidden = true;
        await prompt.prompt();
    });
    window.addEventListener('appinstalled', () => {
        installPrompt = null;
        if (button) button.hidden = true;
    });
})();
