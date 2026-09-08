/* Authentication plus continuous-reader state (server-DB backed; content caching only is local). */

const API_BASE = (window.APP_BASE_PATH || '') + '/api';
const READER_DB = 'summra-reader-v2';
let currentUser = null;
let wrongAccountEmail = null;
let authInitializationPromise = null;
let readerDbPromise = null;
// A mutation only needs a stable identity for the lifetime of this tab (the
// server dedups by mutation_id and conflict-checks by revision, not by
// continuity of device_sequence across sessions), so these are in-memory only.
let sessionDeviceId = null;
let nextDeviceSequence = 1;

function randomId(prefix) {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return `${prefix}_${crypto.randomUUID()}`;
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

function signinUrl() {
    const base = (window.APP_BASE_PATH || '') + '/login';
    return base + '?logout=' + encodeURIComponent(base);
}

function requestPromise(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function transactionPromise(transaction) {
    return new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
    });
}

// Content caching only (already-fetched manifests/segments) so a mid-session
// network hiccup doesn't lose a page the reader already loaded. Reading
// progress itself is never read from or written to this database — it is
// always the server DB (see queueReaderMutation/getReaderState below).
function readerDb() {
    if (readerDbPromise) return readerDbPromise;
    readerDbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(READER_DB, 2);
        request.onupgradeneeded = () => {
            const db = request.result;
            for (const stale of ['device_profile', 'identity_cache', 'local_book_state', 'local_mode_state', 'pending_mutation', 'cached_library', 'sync_decision']) {
                if (db.objectStoreNames.contains(stale)) db.deleteObjectStore(stale);
            }
            if (!db.objectStoreNames.contains('cached_manifest')) db.createObjectStore('cached_manifest', { keyPath: ['book_id', 'content_version'] });
            if (!db.objectStoreNames.contains('cached_segment')) db.createObjectStore('cached_segment', { keyPath: ['book_id', 'content_version', 'mode', 'segment_id'] });
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
    return readerDbPromise;
}

async function queueReaderMutation(input) {
    if (!currentUser) return null;
    sessionDeviceId ||= randomId('device');
    const body = {
        ...input, mutation_id: randomId('mutation'), device_id: sessionDeviceId,
        device_sequence: nextDeviceSequence++, client_occurred_at: new Date().toISOString(),
    };
    try {
        const response = await fetch(`${API_BASE}/progress/v2/mutations`, {
            method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await response.json().catch(() => null);
        if (!data) return null;
        if (data.success && (data.result === 'accepted' || data.result === 'duplicate' || response.status === 409)) {
            return { ...input, base_revision: input.base_revision, projection: data.projection, conflict: response.status === 409 };
        }
    } catch (_) { /* best effort; the reader keeps its in-memory position and will resync from the server on next read */ }
    return null;
}

async function getReaderState(bookId) {
    if (!currentUser) return { book: null, modes: [] };
    try {
        const response = await fetch(`${API_BASE}/progress/v2/books/${bookId}`, {
            credentials: 'include', cache: 'no-store',
        });
        if (response.ok) {
            const data = await response.json();
            return data.projection;
        }
    } catch (_) { /* no server state available right now */ }
    return { book: null, modes: [] };
}

async function getLibrary() {
    if (!currentUser) return { success: true, continue_reading: [], finished: [] };
    try {
        const response = await fetch(`${API_BASE}/library`, {
            credentials: 'include', cache: 'no-store',
        });
        if (response.ok) return await response.json();
    } catch (_) { /* fall through */ }
    return { success: true, continue_reading: [], finished: [] };
}

async function cacheReaderManifest(manifest) {
    if (!manifest?.book?.id || !manifest?.content_version) return;
    const db = await readerDb();
    const tx = db.transaction('cached_manifest', 'readwrite');
    tx.objectStore('cached_manifest').put({
        book_id: manifest.book.id, content_version: manifest.content_version,
        manifest, cached_at: new Date().toISOString(),
    });
    await transactionPromise(tx);
}

async function getCachedReaderManifest(bookId) {
    const db = await readerDb();
    const tx = db.transaction('cached_manifest', 'readonly');
    const all = await requestPromise(tx.objectStore('cached_manifest').getAll());
    await transactionPromise(tx);
    return all.filter(item => item.book_id === bookId)
        .sort((a, b) => b.content_version - a.content_version)[0]?.manifest || null;
}

async function cacheReaderSegment(bookId, segment) {
    if (!segment?.id || !segment?.content_version || !segment?.mode) return;
    const db = await readerDb();
    const tx = db.transaction('cached_segment', 'readwrite');
    tx.objectStore('cached_segment').put({
        book_id: bookId, content_version: segment.content_version, mode: segment.mode,
        segment_id: segment.id, segment, cached_at: new Date().toISOString(),
    });
    await transactionPromise(tx);
}

async function getCachedReaderSegment(bookId, contentVersion, mode, segmentId) {
    const db = await readerDb();
    const tx = db.transaction('cached_segment', 'readonly');
    const row = await requestPromise(tx.objectStore('cached_segment').get([bookId, contentVersion, mode, segmentId]));
    await transactionPromise(tx);
    return row?.segment || null;
}

async function initAuth() {
    if (authInitializationPromise) return authInitializationPromise;
    authInitializationPromise = (async () => {
        await checkAuthStatus();
        setupAuthEventListeners();
        updateAuthUI();
    })();
    await authInitializationPromise;
}

async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE}/auth/check`, {
            credentials: 'include', cache: 'no-store',
        });
        if (response.status === 403) {
            wrongAccountEmail = (await response.json().catch(() => ({}))).email || null;
            currentUser = null;
            return;
        }
        const data = await response.json();
        wrongAccountEmail = null;
        currentUser = data.authenticated ? data.user : null;
    } catch (_) { /* anonymous reading stays available; no progress persistence without an account */ }
}

function setupAuthEventListeners() {
    document.getElementById('user-account-btn')?.addEventListener('click', showUserModal);
    document.getElementById('user-modal-close')?.addEventListener('click', hideUserModal);
    document.getElementById('user-modal-overlay')?.addEventListener('click', hideUserModal);
}

async function showUserModal() {
    const modal = document.getElementById('user-modal');
    if (!modal) return;
    document.getElementById('account-view')?.classList.toggle('hidden', !currentUser);
    document.getElementById('signed-out-view')?.classList.toggle('hidden', !!currentUser);
    const email = document.getElementById('account-email');
    if (email && currentUser) email.textContent = currentUser.email;
    document.getElementById('account-email-row')?.classList.toggle('hidden', !currentUser?.email);
    modal.classList.remove('hidden');
    if (!currentUser) return;

    const inProgress = document.getElementById('books-in-progress-count');
    const finished = document.getElementById('books-finished-count');
    if (inProgress) inProgress.textContent = '…';
    if (finished) finished.textContent = '…';
    const createdRow = document.getElementById('account-created-row');
    const created = document.getElementById('account-created');
    const createdAt = currentUser.created_at || currentUser.createdAt;
    if (createdRow) createdRow.classList.toggle('hidden', !createdAt);
    if (created && createdAt) created.textContent = new Date(createdAt).toLocaleDateString();
    try {
        const library = await getLibrary();
        if (inProgress) inProgress.textContent = String(library.continue_reading?.length || 0);
        if (finished) finished.textContent = String(library.finished?.length || 0);
    } catch (_) {
        if (inProgress) inProgress.textContent = '0';
        if (finished) finished.textContent = '0';
    }
}

function hideUserModal() { document.getElementById('user-modal')?.classList.add('hidden'); }

function updateAuthUI() {
    const account = document.getElementById('user-account-btn');
    const name = document.getElementById('header-user-name');
    if (account && name) {
        name.textContent = currentUser?.email || 'Account';
        account.classList.toggle('hidden', !currentUser);
    }
    const signin = document.getElementById('footer-signin-link');
    if (signin) { signin.href = signinUrl(); signin.classList.toggle('hidden', !!currentUser); }
    document.getElementById('library-nav-btn')?.classList.toggle('hidden', !currentUser);
    const banner = document.getElementById('wrong-account-banner');
    if (banner) {
        banner.textContent = wrongAccountEmail ? `Signed in as ${wrongAccountEmail}, which isn't authorized for Summra.` : '';
        banner.classList.toggle('hidden', !wrongAccountEmail);
    }
}

window.authModule = {
    initAuth, checkAuthStatus, currentUser: () => currentUser,
    queueReaderMutation, getReaderState, getLibrary,
    cacheReaderManifest, getCachedReaderManifest, cacheReaderSegment, getCachedReaderSegment,
    // Legacy chapter pages can remain viewable while their routes redirect to
    // the continuous reader. They intentionally no longer persist v1 data.
    getReadingProgress: async () => null,
    getCompletedChaptersForBook: async () => [],
    trackChapterView: async () => {}, trackPageChange: async () => {}, onChapterComplete: async () => {},
};
