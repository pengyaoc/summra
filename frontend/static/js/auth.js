/**
 * User Authentication and Reading Progress Module
 *
 * Handles user login, registration, session management, and reading progress tracking.
 *
 * Gated by window.FEATURE_AUTH. When the flag is off this module is a no-op:
 * window.authModule is never assigned, so every `if (window.authModule)` check
 * in app.js naturally skips. No /api/auth/* or /api/progress/* fetches fire.
 */

if (window.FEATURE_AUTH) {

// Loads before app.js, so it can't rely on app.js's summraBasePath() helper —
// reads window.APP_BASE_PATH directly instead. See app.js for the full explanation
// of how this supports being reverse-proxied under a URL prefix (e.g. /summrabook).
const API_BASE = (window.APP_BASE_PATH || '') + '/api';

// Auth state
let currentUser = null;
let authInitialized = false;

// Local storage keys for offline support
const STORAGE_KEYS = {
    OFFLINE_PROGRESS: 'summra_offline_progress',
    OFFLINE_COMPLETED: 'summra_offline_completed',
    LAST_SYNC: 'summra_last_sync',
    CURRENT_USER: 'summra_current_user'
};

/**
 * Initialize authentication system
 */
async function initAuth() {
    if (authInitialized) return;

    authInitialized = true;

    // Try to restore from localStorage first (for instant offline support)
    const cachedUser = localStorage.getItem(STORAGE_KEYS.CURRENT_USER);
    if (cachedUser) {
        try {
            currentUser = JSON.parse(cachedUser);
            updateAuthUI(); // Show user as logged in immediately
        } catch (error) {
            console.error('Error parsing cached user:', error);
            localStorage.removeItem(STORAGE_KEYS.CURRENT_USER);
        }
    }

    // Check if user is logged in (verify with server)
    await checkAuthStatus();

    // Set up event listeners
    setupAuthEventListeners();

    // Update UI based on auth status
    updateAuthUI();
}

/**
 * Save current user to localStorage
 */
function setCurrentUser(user) {
    currentUser = user;
    if (user) {
        localStorage.setItem(STORAGE_KEYS.CURRENT_USER, JSON.stringify(user));
    } else {
        localStorage.removeItem(STORAGE_KEYS.CURRENT_USER);
    }
}

/**
 * Check if user is authenticated
 */
async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE}/auth/check`, {
            credentials: 'include'
        });

        const data = await response.json();

        if (data.authenticated) {
            setCurrentUser(data.user);
            // Sync offline progress when user logs in
            await syncOfflineProgress();
        } else {
            setCurrentUser(null);
        }
    } catch (error) {
        console.error('Error checking auth status:', error);

        // Don't clear currentUser if we're offline and have cached state
        // This supports extended offline PWA usage
        if (currentUser) {
            console.log('Offline: Using cached auth state from localStorage');
            // Keep existing currentUser - don't overwrite
        } else {
            setCurrentUser(null);
        }
    }
}

/**
 * Set up event listeners for auth UI
 */
function setupAuthEventListeners() {
    // Account button
    const accountBtn = document.getElementById('user-account-btn');
    if (accountBtn) {
        accountBtn.addEventListener('click', showUserModal);
    }

    // Modal close button
    const closeBtn = document.getElementById('user-modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideUserModal);
    }

    // Modal overlay
    const overlay = document.getElementById('user-modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', hideUserModal);
    }

}

/**
 * Show user modal
 */
function showUserModal() {
    const modal = document.getElementById('user-modal');
    if (!modal) return;

    // Show appropriate view based on auth status
    if (currentUser) {
        switchView('account');
        updateAccountView();
    } else {
        switchView('signed-out');
    }

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

/**
 * Hide user modal
 */
function hideUserModal() {
    const modal = document.getElementById('user-modal');
    if (!modal) return;

    modal.classList.add('hidden');
    document.body.style.overflow = '';
}

/**
 * Switch between signed-out/account views
 */
function switchView(viewName) {
    const views = {
        'signed-out': document.getElementById('signed-out-view'),
        'account': document.getElementById('account-view')
    };

    // Hide all views
    Object.values(views).forEach(view => {
        if (view) view.classList.add('hidden');
    });

    // Show requested view
    if (views[viewName]) {
        views[viewName].classList.remove('hidden');
    }
}

/**
 * Update auth UI elements
 */
function updateAuthUI() {
    const accountBtn = document.getElementById('user-account-btn');
    const userName = document.getElementById('header-user-name');

    if (accountBtn && userName) {
        if (currentUser) {
            userName.textContent = currentUser.email;
            accountBtn.classList.add('logged-in');
            // Only a genuinely signed-in visitor (via the shared gateway
            // elsewhere on pengyaochen.com) ever sees this — there's no
            // sign-in action this app can offer an anonymous one, so the
            // button stays hidden (see the template's default `hidden`
            // attribute) rather than showing a dead end.
            accountBtn.hidden = false;
        } else {
            userName.textContent = 'Account';
            accountBtn.classList.remove('logged-in');
            accountBtn.hidden = true;
        }
    }
}

/**
 * Update account view with user data
 */
async function updateAccountView() {
    if (!currentUser) return;

    // Update basic info
    const emailEl = document.getElementById('account-email');
    if (emailEl) emailEl.textContent = currentUser.email;

    const createdEl = document.getElementById('account-created');
    if (createdEl && currentUser.created_at) {
        createdEl.textContent = new Date(currentUser.created_at).toLocaleDateString();
    }

    // Fetch and update reading stats
    try {
        const response = await fetch(`${API_BASE}/progress/all`, {
            credentials: 'include'
        });

        const data = await response.json();

        if (data.success && data.progress) {
            const booksStarted = new Set(data.progress.map(p => p.book_id)).size;
            const booksStartedEl = document.getElementById('books-started-count');
            if (booksStartedEl) booksStartedEl.textContent = booksStarted;
        }
    } catch (error) {
        console.error('Error fetching reading stats:', error);
    }
}

// ===== Reading Progress Functions =====

/**
 * Save reading progress
 */
async function saveReadingProgress(bookId, chapterNumber, pageNumber = 0, scrollPosition = 0) {
    const progress = {
        book_id: bookId,
        chapter_number: chapterNumber,
        page_number: pageNumber,
        scroll_position: scrollPosition,
        timestamp: new Date().toISOString()
    };

    if (currentUser) {
        // Save to server
        try {
            await fetch(`${API_BASE}/progress/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify(progress)
            });
        } catch (error) {
            console.error('Error saving progress:', error);
            // Fallback to local storage
            saveProgressOffline(progress);
        }
    } else {
        // Save to local storage
        saveProgressOffline(progress);
    }
}

/**
 * Get reading progress for a book
 */
async function getReadingProgress(bookId) {
    if (currentUser) {
        // Fetch from server
        try {
            const response = await fetch(`${API_BASE}/progress/get/${bookId}`, {
                credentials: 'include'
            });

            const data = await response.json();
            return data.progress;
        } catch (error) {
            console.error('Error fetching progress:', error);
            return getProgressOffline(bookId);
        }
    } else {
        // Get from local storage
        return getProgressOffline(bookId);
    }
}

/**
 * Mark chapter as complete
 */
async function markChapterComplete(bookId, chapterNumber, completed = true) {
    const completion = {
        book_id: bookId,
        chapter_number: chapterNumber,
        completed: completed,
        timestamp: new Date().toISOString()
    };

    if (currentUser) {
        // Save to server
        try {
            await fetch(`${API_BASE}/progress/chapter/complete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify(completion)
            });
        } catch (error) {
            console.error('Error marking chapter complete:', error);
            // Fallback to local storage
            saveCompletionOffline(completion);
        }
    } else {
        // Save to local storage
        saveCompletionOffline(completion);
    }
}

/**
 * Get completed chapters for a book
 */
async function getCompletedChapters(bookId) {
    if (currentUser) {
        // Fetch from server
        try {
            const response = await fetch(`${API_BASE}/progress/chapters/${bookId}`, {
                credentials: 'include'
            });

            const data = await response.json();
            return data.completed_chapters || [];
        } catch (error) {
            console.error('Error fetching completed chapters:', error);
            return getCompletedOffline(bookId);
        }
    } else {
        // Get from local storage
        return getCompletedOffline(bookId);
    }
}

// ===== Offline Storage Functions =====

/**
 * Save progress to local storage
 */
function saveProgressOffline(progress) {
    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_PROGRESS) || '[]');

        // Update or add progress entry
        const index = stored.findIndex(p =>
            p.book_id === progress.book_id
        );

        if (index >= 0) {
            stored[index] = progress;
        } else {
            stored.push(progress);
        }

        localStorage.setItem(STORAGE_KEYS.OFFLINE_PROGRESS, JSON.stringify(stored));
    } catch (error) {
        console.error('Error saving offline progress:', error);
    }
}

/**
 * Get progress from local storage
 */
function getProgressOffline(bookId) {
    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_PROGRESS) || '[]');
        return stored.find(p => p.book_id === bookId) || null;
    } catch (error) {
        console.error('Error getting offline progress:', error);
        return null;
    }
}

/**
 * Save chapter completion to local storage
 */
function saveCompletionOffline(completion) {
    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_COMPLETED) || '[]');

        // Update or add completion entry
        const index = stored.findIndex(c =>
            c.book_id === completion.book_id &&
            c.chapter_number === completion.chapter_number
        );

        if (index >= 0) {
            stored[index] = completion;
        } else {
            stored.push(completion);
        }

        localStorage.setItem(STORAGE_KEYS.OFFLINE_COMPLETED, JSON.stringify(stored));
    } catch (error) {
        console.error('Error saving offline completion:', error);
    }
}

/**
 * Get completed chapters from local storage
 */
function getCompletedOffline(bookId) {
    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_COMPLETED) || '[]');
        return stored
            .filter(c => c.book_id === bookId && c.completed)
            .map(c => c.chapter_number);
    } catch (error) {
        console.error('Error getting offline completions:', error);
        return [];
    }
}

/**
 * Sync offline progress with server
 */
async function syncOfflineProgress() {
    if (!currentUser) return;

    try {
        const offlineProgress = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_PROGRESS) || '[]');
        const offlineCompleted = JSON.parse(localStorage.getItem(STORAGE_KEYS.OFFLINE_COMPLETED) || '[]');

        if (offlineProgress.length === 0 && offlineCompleted.length === 0) {
            return;
        }

        const response = await fetch(`${API_BASE}/progress/sync`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                progress: offlineProgress,
                completed_chapters: offlineCompleted
            })
        });

        if (response.ok) {
            // Clear offline storage after successful sync
            localStorage.removeItem(STORAGE_KEYS.OFFLINE_PROGRESS);
            localStorage.removeItem(STORAGE_KEYS.OFFLINE_COMPLETED);
            localStorage.setItem(STORAGE_KEYS.LAST_SYNC, new Date().toISOString());

            console.log('Offline progress synced successfully');
        }
    } catch (error) {
        console.error('Error syncing offline progress:', error);
    }
}

// Export functions for use in app.js
window.authModule = {
    initAuth,
    checkAuthStatus,
    currentUser: () => currentUser,
    saveReadingProgress,
    getReadingProgress,
    markChapterComplete,
    getCompletedChapters,
    syncOfflineProgress
};

// ===== Integration Hooks for Reading Progress =====

/**
 * Hook to track reading progress when a chapter is viewed
 * Call this function from showChapterDetail in app.js
 */
window.authModule.trackChapterView = async function(bookId, chapterNumber, pageNumber = 0) {
    if (!bookId || chapterNumber === null || chapterNumber === undefined) return;

    // Save progress when chapter is viewed
    await saveReadingProgress(bookId, chapterNumber, pageNumber, 0);
};

/**
 * Hook to track page changes in pagination
 * Call this function when page changes in pagination system
 */
window.authModule.trackPageChange = async function(bookId, chapterNumber, pageNumber) {
    if (!bookId || chapterNumber === null || chapterNumber === undefined) return;

    await saveReadingProgress(bookId, chapterNumber, pageNumber, 0);
};

/**
 * Hook to mark chapter as completed when user reads to the end
 * Call this function when user reaches last page of chapter
 */
window.authModule.onChapterComplete = async function(bookId, chapterNumber) {
    if (!bookId || chapterNumber === null || chapterNumber === undefined) return;

    await markChapterComplete(bookId, chapterNumber, true);
};

/**
 * Hook to get reading progress when loading a book/chapter
 * Returns the last chapter and page number
 */
window.authModule.getLastReadPosition = async function(bookId) {
    if (!bookId) return null;

    const progress = await getReadingProgress(bookId);
    return progress;
};

/**
 * Hook to check if a chapter is completed
 * Returns array of completed chapter numbers
 */
window.authModule.getCompletedChaptersForBook = async function(bookId) {
    if (!bookId) return [];

    return await getCompletedChapters(bookId);
};

/**
 * Auto-scroll to last read position
 * Call this after chapter content is rendered
 */
window.authModule.scrollToLastPosition = function(scrollPosition) {
    if (scrollPosition && scrollPosition > 0) {
        setTimeout(() => {
            window.scrollTo({
                top: scrollPosition,
                behavior: 'smooth'
            });
        }, 100);
    }
};

} // end if (window.FEATURE_AUTH)

