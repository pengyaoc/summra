// "Save for Offline" PWA feature: book-caching status checks, listing
// offline-saved books, and driving the service worker's message-based
// download/cache flow for a given book.
//
// Extracted from app.js's single SummraApp class (2026-09 refactor) as a
// plain object of methods, merged onto SummraApp.prototype via
// Object.assign in app.js — see pagination.js's header comment and
// frontend/static/js/README.md for the pattern.
export const offlineMixin = {
    setupSaveOfflineButton() {
        /**
         * Setup "Save for Offline" button for PWA offline book caching
         * Only shows on mobile devices in PWA standalone mode.
         * Gated by FEATURE_AUTH — the button markup is server-stripped when off.
         */
        if (!window.FEATURE_AUTH) {
            return;
        }
        const saveOfflineBtn = document.getElementById('save-offline-btn');
        const saveOfflineText = document.getElementById('save-offline-text');

        if (!saveOfflineBtn || !this.currentBook) {
            return;
        }

        // Check if running in standalone PWA mode (installed app)
        const isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                           window.navigator.standalone || // iOS Safari
                           document.referrer.includes('android-app://'); // Android TWA

        // Check if mobile device
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        // Only show on mobile devices in standalone PWA mode
        if (!isMobile || !isStandalone) {
            saveOfflineBtn.classList.add('hidden');
            return;
        }

        // Check if service worker is available
        if (!('serviceWorker' in navigator)) {
            saveOfflineBtn.classList.add('hidden');
            return;
        }

        // Show button only if service worker is ready
        navigator.serviceWorker.ready.then(async (registration) => {
            saveOfflineBtn.classList.remove('hidden');

            // Check if this book is already cached
            const cacheStatus = await this.checkBookCached(this.currentBook.id);

            if (cacheStatus.isCached) {
                saveOfflineBtn.classList.add('saved');
                saveOfflineText.textContent = 'Saved ✓';
                saveOfflineBtn.disabled = true;
            } else {
                saveOfflineBtn.classList.remove('saved');
                saveOfflineText.textContent = 'Save for Offline';
                saveOfflineBtn.disabled = false;

                // Check if cache was evicted (marker existed but content gone)
                if (cacheStatus.evicted) {
                    console.warn('Book was previously saved but cache was evicted by iOS');

                    // Show user-friendly notification
                    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                    if (isIOS) {
                        console.log('💡 Cache was cleared by iOS. Re-download this book to read offline.');
                        // Update button text to indicate re-download needed
                        saveOfflineText.textContent = 'Re-download for Offline';
                    }
                }

                // Setup click handler
                saveOfflineBtn.onclick = async () => {
                    await this.downloadBookForOffline(this.currentBook);
                };
            }
        }).catch(error => {
            console.error('Service worker not ready:', error);
            saveOfflineBtn.classList.add('hidden');
        });
    },

    async checkBookCached(bookId) {
        /**
         * Check if a book is already cached in the service worker
         * Now verifies actual content exists, not just marker
         * @param {number} bookId - The book ID to check
         * @returns {Promise<{isCached: boolean, evicted: boolean}>} - Cache status
         */
        if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
            return { isCached: false, evicted: false };
        }

        return new Promise((resolve) => {
            const messageChannel = new MessageChannel();

            messageChannel.port1.onmessage = (event) => {
                if (event.data.type === 'BOOK_CACHE_STATUS') {
                    resolve({
                        isCached: event.data.isCached || false,
                        evicted: event.data.evicted || false
                    });
                }
            };

            navigator.serviceWorker.controller.postMessage({
                type: 'CHECK_BOOK_CACHED',
                bookId: bookId
            }, [messageChannel.port2]);

            // Timeout after 2 seconds
            setTimeout(() => resolve({ isCached: false, evicted: false }), 2000);
        });
    },

    async getOfflineBooks() {
        /**
         * Get list of all offline-saved book IDs from service worker
         * Now includes verification and eviction detection
         * Gated by FEATURE_AUTH — Save-for-Offline is part of the auth bundle.
         * @returns {Promise<{bookIds: number[], evictedBookIds: number[]}>} - Cached and evicted book IDs
         */
        if (!window.FEATURE_AUTH) {
            return { bookIds: [], evictedBookIds: [] };
        }
        if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
            return { bookIds: [], evictedBookIds: [] };
        }

        return new Promise((resolve) => {
            const messageChannel = new MessageChannel();

            messageChannel.port1.onmessage = (event) => {
                if (event.data.type === 'OFFLINE_BOOKS_LIST') {
                    resolve({
                        bookIds: event.data.bookIds || [],
                        evictedBookIds: event.data.evictedBookIds || []
                    });
                }
            };

            navigator.serviceWorker.controller.postMessage({
                type: 'GET_OFFLINE_BOOKS'
            }, [messageChannel.port2]);

            // Timeout after 2 seconds
            setTimeout(() => resolve({ bookIds: [], evictedBookIds: [] }), 2000);
        });
    },

    async downloadBookForOffline(book) {
        /**
         * Download all book content for offline reading
         * @param {Object} book - The book object to cache
         */
        const saveOfflineBtn = document.getElementById('save-offline-btn');
        const saveOfflineText = document.getElementById('save-offline-text');

        if (!saveOfflineBtn || !('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
            alert('Offline functionality not available');
            return;
        }

        // Update button to loading state
        saveOfflineBtn.disabled = true;
        saveOfflineBtn.classList.add('loading');
        saveOfflineText.textContent = 'Downloading...';

        try {
            const messageChannel = new MessageChannel();
            let progressReceived = false;

            messageChannel.port1.onmessage = (event) => {
                if (event.data.type === 'CACHE_PROGRESS') {
                    progressReceived = true;
                    const percent = Math.round((event.data.cached / event.data.total) * 100);
                    saveOfflineText.textContent = `Downloading... ${percent}%`;
                } else if (event.data.type === 'CACHE_COMPLETE') {
                    if (event.data.success) {
                        saveOfflineBtn.classList.remove('loading');
                        saveOfflineBtn.classList.add('saved');
                        saveOfflineText.textContent = 'Saved ✓';
                        console.log(`✅ Book cached: ${event.data.cached}/${event.data.total} resources (${event.data.failed} failed)`);
                    } else {
                        saveOfflineBtn.classList.remove('loading');
                        saveOfflineBtn.disabled = false;
                        saveOfflineText.textContent = 'Save for Offline';
                        alert(`Failed to save book: ${event.data.error}`);
                    }
                }
            };

            // Send message to service worker to cache the book
            const bookSlug = book.slug || this.slugify(book.title);
            navigator.serviceWorker.controller.postMessage({
                type: 'CACHE_BOOK',
                bookId: book.id,
                bookSlug: bookSlug
            }, [messageChannel.port2]);

            // Timeout if no progress received after 30 seconds
            setTimeout(() => {
                if (!progressReceived) {
                    saveOfflineBtn.classList.remove('loading');
                    saveOfflineBtn.disabled = false;
                    saveOfflineText.textContent = 'Save for Offline';
                    alert('Download timed out. Please try again.');
                }
            }, 30000);
        } catch (error) {
            console.error('Error downloading book for offline:', error);
            saveOfflineBtn.classList.remove('loading');
            saveOfflineBtn.disabled = false;
            saveOfflineText.textContent = 'Save for Offline';
            alert('Failed to save book for offline. Please try again.');
        }
    }

};
