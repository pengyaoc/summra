/* Authentication plus local-first continuous-reader state. */

const API_BASE = (window.APP_BASE_PATH || '') + '/api';
const READER_DB = 'summra-reader-v2';
const PROFILE_KEY = 'profile';
let currentUser = null;
let wrongAccountEmail = null;
let authInitialized = false;
let readerDbPromise = null;

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

function readerDb() {
    if (readerDbPromise) return readerDbPromise;
    readerDbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(READER_DB, 1);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains('device_profile')) db.createObjectStore('device_profile', { keyPath: 'scope' });
            if (!db.objectStoreNames.contains('identity_cache')) db.createObjectStore('identity_cache', { keyPath: 'scope' });
            if (!db.objectStoreNames.contains('local_book_state')) db.createObjectStore('local_book_state', { keyPath: 'book_id' });
            if (!db.objectStoreNames.contains('local_mode_state')) db.createObjectStore('local_mode_state', { keyPath: ['book_id', 'mode'] });
            if (!db.objectStoreNames.contains('pending_mutation')) {
                const store = db.createObjectStore('pending_mutation', { keyPath: 'mutation_id' });
                store.createIndex('by_status', 'queue_status');
                store.createIndex('by_sequence', ['device_id', 'device_sequence'], { unique: true });
            }
            if (!db.objectStoreNames.contains('cached_library')) db.createObjectStore('cached_library', { keyPath: 'scope' });
            if (!db.objectStoreNames.contains('cached_manifest')) db.createObjectStore('cached_manifest', { keyPath: ['book_id', 'content_version'] });
            if (!db.objectStoreNames.contains('cached_segment')) db.createObjectStore('cached_segment', { keyPath: ['book_id', 'content_version', 'mode', 'segment_id'] });
            if (!db.objectStoreNames.contains('sync_decision')) db.createObjectStore('sync_decision', { keyPath: ['book_id', 'mode', 'remote_revision'] });
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
    return readerDbPromise;
}

function randomId(prefix) {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return `${prefix}_${crypto.randomUUID()}`;
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

async function getProfile(store) {
    let profile = await requestPromise(store.get(PROFILE_KEY));
    if (!profile) {
        profile = { scope: PROFILE_KEY, schema_version: 1, device_id: randomId('device'), next_device_sequence: 1, created_at: new Date().toISOString() };
        store.put(profile);
    }
    return profile;
}

async function queueReaderMutation(input) {
    const db = await readerDb();
    const tx = db.transaction(['device_profile', 'local_book_state', 'local_mode_state', 'pending_mutation'], 'readwrite');
    const profileStore = tx.objectStore('device_profile');
    const bookStore = tx.objectStore('local_book_state');
    const modeStore = tx.objectStore('local_mode_state');
    const mutationStore = tx.objectStore('pending_mutation');
    const profile = await getProfile(profileStore);
    const sequence = profile.next_device_sequence;
    profile.next_device_sequence += 1;
    profileStore.put(profile);

    const now = new Date().toISOString();
    const existingBook = await requestPromise(bookStore.get(input.book_id));
    const existingMode = await requestPromise(modeStore.get([input.book_id, input.mode]));
    const current = input.current_marker;
    const furthest = input.qualified_furthest_marker || existingMode?.furthest_marker || null;
    const localMode = {
        book_id: input.book_id, mode: input.mode, content_version: current.content_version,
        current_marker: current, furthest_marker: furthest,
        active_reading_seconds: (existingMode?.active_reading_seconds || 0) + (input.active_seconds_delta || 0),
        sequential_boundary_count: (existingMode?.sequential_boundary_count || 0) + (input.sequential_boundaries_delta || 0),
        // Keep a speculative per-mode revision so queued mutations from one
        // device are submitted in the exact order the server expects.
        server_revision: (existingMode?.server_revision ?? input.base_revision ?? 0) + 1,
        last_device_id: profile.device_id, updated_at: now,
    };
    const meaningful = localMode.sequential_boundary_count >= 2 ||
        (localMode.active_reading_seconds >= 60 && current.ordinal > 0);
    const bookState = {
        book_id: input.book_id, last_mode: input.mode,
        status: input.event_cause === 'manual_unfinish' ? 'in_progress' : (existingBook?.status || (meaningful ? 'in_progress' : 'preview')),
        meaningfully_started_at: existingBook?.meaningfully_started_at || (meaningful ? now : null),
        last_meaningful_read_at: meaningful ? now : (existingBook?.last_meaningful_read_at || null),
        finished_at: existingBook?.finished_at || null,
        manual_unfinished_at: input.event_cause === 'manual_unfinish' ? now : (existingBook?.manual_unfinished_at || null),
        server_revision: (existingBook?.server_revision ?? input.base_revision ?? 0) + 1,
        updated_at: now,
    };
    if (input.event_cause === 'completion') {
        bookState.status = 'finished';
        bookState.finished_at = now;
    }
    bookStore.put(bookState);
    modeStore.put(localMode);
    const mutation = {
        ...input, mutation_id: randomId('mutation'), device_id: profile.device_id,
        device_sequence: sequence, base_revision: existingMode?.server_revision ?? input.base_revision ?? 0,
        client_occurred_at: now, queue_status: 'pending', retry_count: 0, next_attempt_at: now,
    };
    mutationStore.put(mutation);
    await transactionPromise(tx);
    flushReaderQueue().catch(() => {});
    return mutation;
}

async function cacheProjection(projection) {
    if (!projection?.book) return;
    const db = await readerDb();
    const tx = db.transaction(['local_book_state', 'local_mode_state'], 'readwrite');
    const book = projection.book;
    tx.objectStore('local_book_state').put({
        book_id: book.book_id, last_mode: book.last_mode, status: book.status,
        meaningfully_started_at: book.meaningfully_started_at, last_meaningful_read_at: book.last_meaningful_read_at,
        finished_at: book.finished_at, manual_unfinished_at: book.manual_unfinished_at,
        server_revision: book.revision, updated_at: book.updated_at,
    });
    for (const mode of projection.modes || []) {
        tx.objectStore('local_mode_state').put({
            book_id: mode.book_id, mode: mode.mode, content_version: mode.content_version,
            current_marker: mode.current_marker, furthest_marker: mode.furthest_marker,
            active_reading_seconds: mode.active_reading_seconds, sequential_boundary_count: mode.sequential_boundary_count,
            server_revision: mode.revision, last_device_id: mode.last_device_id, updated_at: mode.updated_at,
        });
    }
    await transactionPromise(tx);
}

async function getReaderState(bookId) {
    if (currentUser && navigator.onLine) {
        try {
            const response = await fetch(`${API_BASE}/progress/v2/books/${bookId}`, { credentials: 'include' });
            if (response.ok) {
                const data = await response.json();
                await cacheProjection(data.projection);
                return data.projection;
            }
        } catch (_) { /* use local state */ }
    }
    const db = await readerDb();
    const tx = db.transaction(['local_book_state', 'local_mode_state'], 'readonly');
    const book = await requestPromise(tx.objectStore('local_book_state').get(bookId));
    const modes = await requestPromise(tx.objectStore('local_mode_state').getAll());
    await transactionPromise(tx);
    return { book: book || null, modes: modes.filter(item => item.book_id === bookId) };
}

async function flushReaderQueue() {
    if (!currentUser || !navigator.onLine) return;
    const db = await readerDb();
    const readTx = db.transaction('pending_mutation', 'readonly');
    const mutations = await requestPromise(readTx.objectStore('pending_mutation').getAll());
    await transactionPromise(readTx);
    for (const mutation of mutations.filter(item => item.queue_status === 'pending')) {
        try {
            const body = { ...mutation };
            delete body.queue_status; delete body.retry_count; delete body.next_attempt_at;
            const response = await fetch(`${API_BASE}/progress/v2/mutations`, {
                method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
            });
            const data = await response.json();
            const writeTx = db.transaction(['pending_mutation', 'local_book_state', 'local_mode_state'], 'readwrite');
            if (data.success && (data.result === 'accepted' || data.result === 'duplicate')) {
                writeTx.objectStore('pending_mutation').delete(mutation.mutation_id);
                if (data.projection) await cacheProjectionInTransaction(writeTx, data.projection);
            } else if (response.status === 409) {
                mutation.queue_status = 'conflict';
                writeTx.objectStore('pending_mutation').put(mutation);
                if (data.projection) await cacheProjectionInTransaction(writeTx, data.projection);
            } else {
                mutation.retry_count += 1;
                mutation.next_attempt_at = new Date(Date.now() + Math.min(60000, 1000 * (2 ** mutation.retry_count))).toISOString();
                writeTx.objectStore('pending_mutation').put(mutation);
            }
            await transactionPromise(writeTx);
        } catch (_) { return; }
    }
}

function cacheProjectionInTransaction(tx, projection) {
    if (!projection?.book) return;
    const book = projection.book;
    tx.objectStore('local_book_state').put({
        book_id: book.book_id, last_mode: book.last_mode, status: book.status,
        meaningfully_started_at: book.meaningfully_started_at, last_meaningful_read_at: book.last_meaningful_read_at,
        finished_at: book.finished_at, manual_unfinished_at: book.manual_unfinished_at,
        server_revision: book.revision, updated_at: book.updated_at,
    });
    for (const mode of projection.modes || []) {
        tx.objectStore('local_mode_state').put({
            book_id: mode.book_id, mode: mode.mode, content_version: mode.content_version,
            current_marker: mode.current_marker, furthest_marker: mode.furthest_marker,
            active_reading_seconds: mode.active_reading_seconds, sequential_boundary_count: mode.sequential_boundary_count,
            server_revision: mode.revision, last_device_id: mode.last_device_id, updated_at: mode.updated_at,
        });
    }
}

async function getLibrary() {
    const scope = currentUser ? `user:${currentUser.id}` : 'device';
    if (currentUser && navigator.onLine) {
        try {
            const response = await fetch(`${API_BASE}/library`, { credentials: 'include' });
            if (response.ok) {
                const data = await response.json();
                const db = await readerDb();
                const tx = db.transaction('cached_library', 'readwrite');
                tx.objectStore('cached_library').put({ scope, projection: data, cached_at: new Date().toISOString() });
                await transactionPromise(tx);
                return data;
            }
        } catch (_) { /* fall through */ }
    }
    const db = await readerDb();
    const tx = db.transaction('cached_library', 'readonly');
    const cached = await requestPromise(tx.objectStore('cached_library').get(scope));
    await transactionPromise(tx);
    return cached?.projection || { success: true, continue_reading: [], finished: [], offline: true };
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
    if (authInitialized) return;
    authInitialized = true;
    await checkAuthStatus();
    setupAuthEventListeners();
    updateAuthUI();
    window.addEventListener('online', () => flushReaderQueue().catch(() => {}));
}

async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE}/auth/check`, { credentials: 'include' });
        if (response.status === 403) {
            wrongAccountEmail = (await response.json().catch(() => ({}))).email || null;
            currentUser = null;
            return;
        }
        const data = await response.json();
        wrongAccountEmail = null;
        currentUser = data.authenticated ? data.user : null;
        if (currentUser) await flushReaderQueue();
    } catch (_) { /* anonymous/local reading stays available */ }
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
        banner.textContent = wrongAccountEmail ? `Signed in as ${wrongAccountEmail}, which isn't authorized for Summra. Reading progress remains on this device.` : '';
        banner.classList.toggle('hidden', !wrongAccountEmail);
    }
}

window.authModule = {
    initAuth, checkAuthStatus, currentUser: () => currentUser,
    queueReaderMutation, flushReaderQueue, getReaderState, getLibrary,
    cacheReaderManifest, getCachedReaderManifest, cacheReaderSegment, getCachedReaderSegment,
    // Legacy chapter pages can remain viewable while their routes redirect to
    // the continuous reader. They intentionally no longer persist v1 data.
    getReadingProgress: async () => null,
    getCompletedChaptersForBook: async () => [],
    trackChapterView: async () => {}, trackPageChange: async () => {}, onChapterComplete: async () => {},
};
