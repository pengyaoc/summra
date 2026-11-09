// In-place page loading: fetch the ordinary page, swap its content, keep everything
// else (scripts, audio, the player) alive. A direct link, refresh or failed fetch is
// an ordinary page load, and the server sends the same HTML either way.
const pages = new Map();
const PROGRESS_AFTER_MS = 150;
const PREFETCH_FRESH_MS = 8000;

let rootSelector, options, root;
let current = null;
let request = null;     // { url, controller, promise, at }
let navigation = 0;
let navigating = false;
let scrollTimer = null;

export function registerPage(name, handlers) { pages.set(name, handlers); }

const canSwap = url => url.origin === location.origin && options.canSwap(url);

function fetchPage(url) {
    if (request?.url === url && Date.now() - request.at < PREFETCH_FRESH_MS) return request;
    request?.controller.abort();
    const controller = new AbortController();
    const promise = fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'page-swap' }, signal: controller.signal }).then(async response => {
        const html = (response.headers.get('content-type') || '').includes('text/html');
        if (!response.ok || response.redirected || !html) throw new Error('not a page');
        return { html: await response.text() };
    });
    promise.catch(() => {});
    request = { url, controller, promise, at: Date.now() };
    return request;
}

async function fullLoad(url) {
    await Promise.race([Promise.resolve(options.beforeFullLoad?.()).catch(() => {}), new Promise(resolve => setTimeout(resolve, 400))]);
    location.assign(url);
}

function rememberScroll() {
    history.replaceState({ ...history.state, scroll: scrollY }, '');
}

async function runCurrent(method, ...args) {
    const page = pages.get(root.dataset.page);
    if (page?.[method]) await page[method](...args);
}

function showPage(next, doc) {
    document.title = doc.title;
    document.documentElement.lang = doc.documentElement.lang;
    document.body.className = next.dataset.bodyClass || '';
    for (const key of Object.keys(root.dataset)) delete root.dataset[key];
    Object.assign(root.dataset, next.dataset);
    root.replaceChildren(...[...next.childNodes].map(node => document.adoptNode(node)));
}

// Load `url` in place. `push` adds a history entry; `scroll` is where to land.
export async function go(url, { push = true, scroll = 0 } = {}) {
    const mine = ++navigation;
    navigating = true;
    const pending = fetchPage(url);
    const timer = setTimeout(() => showProgress(true), PROGRESS_AFTER_MS);
    let page;
    try {
        page = await pending.promise;
    } catch (_) {
        if (mine === navigation) { clearTimeout(timer); showProgress(false); navigating = false; await fullLoad(url); }
        return;
    }
    if (mine !== navigation) { clearTimeout(timer); return; }
    clearTimeout(timer);
    showProgress(false);
    navigating = false;
    request = null;
    const doc = new DOMParser().parseFromString(page.html, 'text/html');
    const next = doc.querySelector(rootSelector);
    if (!next) { await fullLoad(url); return; }
    if (push) { rememberScroll(); history.pushState({ scroll: 0 }, '', url); }
    await current;
    await runCurrent('stop');
    if (mine !== navigation) return;
    showPage(next, doc);
    const target = new URL(url, location.href).hash.slice(1);
    const anchor = !scroll && target ? document.getElementById(target) : null;
    if (anchor) anchor.scrollIntoView(); else scrollTo(0, scroll);
    current = Promise.resolve(runCurrent('start', root)).catch(() => {});
}

function showProgress(visible) {
    let line = document.getElementById('page-progress');
    if (!visible) { line?.remove(); return; }
    if (line) return;
    line = document.createElement('div');
    line.id = 'page-progress';
    line.className = 'page-progress';
    document.body.append(line);
}

function linkFrom(event) {
    const link = event.target.closest?.('a[href]');
    if (!link || !root.contains(link) || link.target || link.hasAttribute('download')) return null;
    const url = new URL(link.href, location.href);
    if (!canSwap(url)) return null;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return null;
    return url;
}

export function startPageSwap({ root: selector, canSwap: allowed, beforeFullLoad }) {
    rootSelector = selector;
    options = { canSwap: allowed, beforeFullLoad };
    root = document.querySelector(selector);
    history.scrollRestoration = 'manual';
    history.replaceState({ ...history.state, scroll: history.state?.scroll || 0 }, '');

    // Start fetching before the tap ends. Never in place of a navigation already under way.
    const prefetch = event => {
        if (navigating) return;
        const url = linkFrom(event);
        if (url) fetchPage(url.href);
    };
    document.addEventListener('pointerdown', prefetch, { passive: true });
    document.addEventListener('mouseover', prefetch, { passive: true });
    document.addEventListener('click', event => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const url = linkFrom(event);
        if (!url) return;
        event.preventDefault();
        go(url.href);
    });
    document.addEventListener('submit', event => {
        const form = event.target;
        if (event.defaultPrevented || !root.contains(form) || form.method.toLowerCase() !== 'get' || form.target) return;
        const url = new URL(form.action, location.href);
        if (!canSwap(url)) return;
        event.preventDefault();
        url.search = new URLSearchParams(new FormData(form, event.submitter)).toString();
        go(url.href);
    });
    window.addEventListener('popstate', event => go(location.href, { push: false, scroll: event.state?.scroll || 0 }));
    window.addEventListener('scroll', () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(rememberScroll, 200);  // Safari limits how often history can change
    }, { passive: true });

    current = Promise.resolve(runCurrent('start', root)).catch(() => {});
}
