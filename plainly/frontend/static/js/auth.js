/* Authentication UI (account modal, sign-in links) on top of window.readerState
   (shared/static/js/reader_state.js, loaded just before this file). */

const { checkAuthStatus, getLibrary } = window.readerState;
let authInitializationPromise = null;

function signinUrl() {
    const base = (window.APP_BASE_PATH || '') + '/login';
    return base + '?logout=' + encodeURIComponent(base);
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

function setupAuthEventListeners() {
    document.getElementById('user-account-btn')?.addEventListener('click', showUserModal);
    document.getElementById('user-modal-close')?.addEventListener('click', hideUserModal);
    document.getElementById('user-modal-overlay')?.addEventListener('click', hideUserModal);
    // The router opens the library; the modal just needs to get out of the way.
    document.getElementById('account-library-link')?.addEventListener('click', hideUserModal);
}

async function showUserModal() {
    const currentUser = window.readerState.currentUser();
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
    const currentUser = window.readerState.currentUser();
    const wrongAccountEmail = window.readerState.wrongAccountEmail();
    const account = document.getElementById('user-account-btn');
    const name = document.getElementById('header-user-name');
    if (account && name) {
        const email = currentUser?.email || '';
        name.textContent = email || 'Account';
        account.setAttribute('aria-label', email ? `Account (${email})` : 'Account');
        account.title = email || 'Account';
        // Avatar: the email's first letter; the person icon stays otherwise.
        const avatar = document.getElementById('account-avatar');
        if (avatar && email) avatar.textContent = email[0].toUpperCase();
        account.classList.toggle('hidden', !currentUser);
    }
    for (const id of ['footer-signin-link', 'header-signin-link']) {
        const signin = document.getElementById(id);
        if (signin) { signin.href = signinUrl(); signin.classList.toggle('hidden', !!currentUser); }
    }
    document.getElementById('library-nav-btn')?.classList.toggle('hidden', !currentUser);
    const banner = document.getElementById('wrong-account-banner');
    if (banner) {
        banner.textContent = wrongAccountEmail ? `Signed in as ${wrongAccountEmail}, which isn't authorized for Plainly.` : '';
        banner.classList.toggle('hidden', !wrongAccountEmail);
    }
}

window.authModule = {
    ...window.readerState,
    initAuth,
    // Legacy chapter pages can remain viewable while their routes redirect to
    // the continuous reader. They intentionally no longer persist v1 data.
    trackChapterView: async () => {}, trackPageChange: async () => {}, onChapterComplete: async () => {},
};
