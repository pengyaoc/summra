// Summra Service Worker - PWA Offline Support
// Uses Workbox for simplified caching strategies

importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-sw.js');

// Deploy-time URL prefix (e.g. '/summrabook' when reverse-proxied under a
// subpath, '' at the root) — injected by Flask's service_worker() route from
// request.script_root. All cache route matchers below must account for it
// since url.pathname includes the live prefix.
const BASE_PATH = "{{ base_path }}";

if (workbox) {
    console.log('Workbox loaded successfully');

    // Configure Workbox
    workbox.setConfig({
        debug: false
    });

    const { precacheAndRoute } = workbox.precaching;
    const { registerRoute } = workbox.routing;
    const { CacheFirst, NetworkFirst, StaleWhileRevalidate, NetworkOnly } = workbox.strategies;
    const { ExpirationPlugin } = workbox.expiration;
    const { CacheableResponsePlugin } = workbox.cacheableResponse;

    // Precache app shell and critical resources. `revision` is a content
    // hash of index.html + offline.html (computed server-side by
    // backend/routes/system.py's _precache_revision(), baked in here at
    // render time) rather than a hand-bumped literal, so editing either
    // template automatically forces Workbox to refetch the precached shell
    // on the next SW install instead of serving a stale one indefinitely.
    precacheAndRoute([
        { url: BASE_PATH + '/', revision: '{{ precache_revision }}' },
        { url: BASE_PATH + '/offline', revision: '{{ precache_revision }}' }
    ]);

    // Cache CSS files - Stale While Revalidate (serve cache instantly, refresh
    // in background). Switched from CacheFirst because the 30-day max-age was
    // pinning broken CSS for returning users after layout changes shipped.
    // SWR self-heals within one navigation cycle even without URL versioning,
    // and templates now also append asset_v('css/...') as a content-hash query
    // string for immediate cache invalidation on deploy.
    registerRoute(
        ({ request }) => request.destination === 'style',
        new StaleWhileRevalidate({
            cacheName: 'css-cache-v2',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 10,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
        })
    );

    // Cache JavaScript files - Stale While Revalidate (check network, update cache)
    registerRoute(
        ({ request }) => request.destination === 'script',
        new StaleWhileRevalidate({
            cacheName: 'js-cache-v2',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 20,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
        })
    );

    // Cache images (book covers, icons, illustrations) - Cache First
    registerRoute(
        ({ request }) => request.destination === 'image',
        new CacheFirst({
            cacheName: 'images-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 100, // Limit to 100 images
                    maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
                }),
            ],
        })
    );

    // Cache fonts - Cache First (long-lived)
    registerRoute(
        ({ request }) => request.destination === 'font',
        new CacheFirst({
            cacheName: 'fonts-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 10,
                    maxAgeSeconds: 365 * 24 * 60 * 60, // 1 year
                }),
            ],
        })
    );

    // Cache auth check endpoint - Network First with long-lived cache for offline support
    // Extended cache duration to support extended offline PWA usage (30 days)
    registerRoute(
        ({ url }) => url.pathname === BASE_PATH + '/api/auth/check',
        new NetworkFirst({
            cacheName: 'auth-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 1,
                    maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days cache (matches session lifetime)
                }),
            ],
            networkTimeoutSeconds: 3, // Fast fallback to cache after 3s
        })
    );

    // Cache book data API - Network First (fresh when online, cached fallback)
    registerRoute(
        ({ url }) => url.pathname.startsWith(BASE_PATH + '/api/books/') && url.pathname.match(/\/api\/books\/\d+$/),
        new NetworkFirst({
            cacheName: 'book-data-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 50, // Cache up to 50 books
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
            networkTimeoutSeconds: 5, // Fallback to cache after 5s
        })
    );

    // Continuous-reader manifests are small and versioned. Prefer a fresh
    // manifest when online, but retain the last one for offline reopening.
    registerRoute(
        ({ url }) => url.pathname.match(/\/api\/reader\/books\/\d+\/manifest$/),
        new NetworkFirst({
            cacheName: 'reader-manifests-v1',
            plugins: [new CacheableResponsePlugin({ statuses: [0, 200] }), new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 7 * 24 * 60 * 60 })],
            networkTimeoutSeconds: 4,
        })
    );

    // Segments are immutable for their content version and may safely be
    // served cache-first once fetched.
    registerRoute(
        ({ url }) => url.pathname.match(/\/api\/reader\/books\/\d+\/segments\/[^/]+$/),
        new CacheFirst({
            cacheName: 'reader-segments-v1',
            plugins: [new CacheableResponsePlugin({ statuses: [0, 200] }), new ExpirationPlugin({ maxEntries: 8000, maxAgeSeconds: 30 * 24 * 60 * 60 })],
        })
    );

    // Cache book summaries - Network First
    registerRoute(
        ({ url }) => url.pathname.match(/\/api\/books\/\d+\/summary\/\w+$/),
        new NetworkFirst({
            cacheName: 'summaries-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 50,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
            networkTimeoutSeconds: 5,
        })
    );

    // Cache book chapters - Network First
    registerRoute(
        ({ url }) => url.pathname.match(/\/api\/books\/\d+\/chapters(\/\d+)?$/),
        new NetworkFirst({
            cacheName: 'chapters-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 100,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
            networkTimeoutSeconds: 5,
        })
    );

    // Cache book lists and categories - Stale While Revalidate (fast + fresh)
    registerRoute(
        ({ url }) => url.pathname === BASE_PATH + '/api/books' ||
                     url.pathname.startsWith(BASE_PATH + '/api/categories') ||
                     url.pathname.startsWith(BASE_PATH + '/api/discover'),
        new StaleWhileRevalidate({
            cacheName: 'lists-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 30,
                    maxAgeSeconds: 24 * 60 * 60, // 1 day
                }),
            ],
        })
    );

    // Cache author data - Stale While Revalidate
    registerRoute(
        ({ url }) => url.pathname.startsWith(BASE_PATH + '/api/authors/'),
        new StaleWhileRevalidate({
            cacheName: 'authors-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 50,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
        })
    );

    // Cache blog posts - Stale While Revalidate
    registerRoute(
        ({ url }) => url.pathname.startsWith(BASE_PATH + '/api/blog'),
        new StaleWhileRevalidate({
            cacheName: 'blog-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
                new ExpirationPlugin({
                    maxEntries: 20,
                    maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
                }),
            ],
        })
    );

    // Never cache TTS generation requests - Network Only
    registerRoute(
        ({ url }) => url.pathname.startsWith(BASE_PATH + '/api/tts/'),
        new NetworkOnly()
    );

    // Never cache admin endpoints - Network Only
    registerRoute(
        ({ url }) => url.pathname.startsWith(BASE_PATH + '/api/admin/'),
        new NetworkOnly()
    );

    // Catch-all for HTML navigation requests - Network First with offline fallback
    registerRoute(
        ({ request }) => request.mode === 'navigate',
        new NetworkFirst({
            cacheName: 'pages-cache',
            plugins: [
                new CacheableResponsePlugin({
                    statuses: [0, 200],
                }),
            ],
            networkTimeoutSeconds: 5,
        })
    );

    // Offline fallback
    workbox.routing.setCatchHandler(async ({ event }) => {
        // Only handle navigation requests (page loads)
        if (event.request.mode === 'navigate') {
            const cache = await caches.open('pages-cache');
            const cachedResponse = await cache.match(BASE_PATH + '/offline');
            return cachedResponse || Response.error();
        }

        return Response.error();
    });

    // Install event - activate immediately
    self.addEventListener('install', (event) => {
        console.log('Service Worker installing...');
        self.skipWaiting();
    });

    // Activate event - claim clients immediately
    self.addEventListener('activate', (event) => {
        console.log('Service Worker activating...');
        event.waitUntil(self.clients.claim());
    });

    // Message event - handle cache requests and other commands
    self.addEventListener('message', async (event) => {
        if (event.data && event.data.type === 'SKIP_WAITING') {
            self.skipWaiting();
            return;
        }

        // Handle book prefetch request
        if (event.data && event.data.type === 'CACHE_BOOK') {
            const { bookId, bookSlug } = event.data;
            console.log(`📥 Caching book ${bookId} for offline reading...`);

            try {
                // Fetch and cache all book resources
                const resourcesToCache = [
                    // Book data
                    `/api/books/${bookId}`,
                    // Summaries
                    `/api/books/${bookId}/summary/concise`,
                    `/api/books/${bookId}/summary/medium`,
                    `/api/books/${bookId}/summary/comprehensive`,
                    // All chapters
                    `/api/books/${bookId}/chapters`
                ];

                // First, fetch the chapters list to know how many there are
                const chaptersResponse = await fetch(`/api/books/${bookId}/chapters`);
                if (chaptersResponse.ok) {
                    const chaptersData = await chaptersResponse.json();

                    // Extract chapters from sections (handling hierarchical structure)
                    const allChapters = [];
                    if (chaptersData.sections) {
                        chaptersData.sections.forEach(section => {
                            if (section.chapters && Array.isArray(section.chapters)) {
                                allChapters.push(...section.chapters);
                            }
                        });
                    }

                    // Add individual chapter endpoints
                    allChapters.forEach(chapter => {
                        resourcesToCache.push(`/api/books/${bookId}/chapters/${chapter.chapter_number}`);
                    });

                    console.log(`📚 Found ${allChapters.length} chapters to cache`);
                }

                // Fetch and cache all resources
                let cached = 0;
                let failed = 0;

                for (const url of resourcesToCache) {
                    try {
                        const response = await fetch(url);
                        if (response.ok) {
                            const cache = await caches.open(getCacheNameForUrl(url));
                            await cache.put(url, response.clone());
                            cached++;

                            // Send progress update
                            if (event.ports && event.ports[0]) {
                                event.ports[0].postMessage({
                                    type: 'CACHE_PROGRESS',
                                    cached,
                                    total: resourcesToCache.length
                                });
                            }
                        }
                    } catch (error) {
                        console.error(`Failed to cache ${url}:`, error);
                        failed++;
                    }
                }

                console.log(`✅ Cached ${cached}/${resourcesToCache.length} resources (${failed} failed)`);

                // Mark this book as explicitly downloaded for offline
                // This creates a marker so we can distinguish between:
                // 1. Books cached automatically via Network-First (browsing)
                // 2. Books explicitly downloaded for offline via "Save for Offline" button
                const offlineCache = await caches.open('offline-books-cache');
                const markerResponse = new Response(JSON.stringify({
                    bookId,
                    bookSlug,
                    cachedAt: new Date().toISOString(),
                    resourceCount: cached
                }), {
                    headers: { 'Content-Type': 'application/json' }
                });
                await offlineCache.put(`/offline-book-marker/${bookId}`, markerResponse);

                // Send completion message
                if (event.ports && event.ports[0]) {
                    event.ports[0].postMessage({
                        type: 'CACHE_COMPLETE',
                        success: true,
                        cached,
                        failed,
                        total: resourcesToCache.length
                    });
                }
            } catch (error) {
                console.error('Error caching book:', error);
                if (event.ports && event.ports[0]) {
                    event.ports[0].postMessage({
                        type: 'CACHE_COMPLETE',
                        success: false,
                        error: error.message
                    });
                }
            }
        }

        // Check if book is cached for offline
        if (event.data && event.data.type === 'CHECK_BOOK_CACHED') {
            const { bookId } = event.data;

            try {
                // Check if this book was explicitly downloaded for offline
                // We use a special cache to track offline downloads
                const offlineCache = await caches.open('offline-books-cache');
                const offlineMarker = await offlineCache.match(`/offline-book-marker/${bookId}`);

                // Marker exists, but verify actual content is still available
                if (offlineMarker) {
                    // Verify critical book data is actually cached
                    const bookDataCache = await caches.open('book-data-cache');
                    const chaptersCache = await caches.open('chapters-cache');

                    // Check if book metadata is cached
                    const bookData = await bookDataCache.match(`/api/books/${bookId}`);
                    // Check if chapters list is cached
                    const chaptersList = await chaptersCache.match(`/api/books/${bookId}/chapters`);

                    // Book is only "cached" if both marker AND actual content exist
                    const isCached = !!(bookData && chaptersList);

                    // If marker exists but content is gone (cache eviction), clean up marker
                    if (!isCached) {
                        console.warn(`Book ${bookId} marker found but content missing - cache was evicted`);
                        await offlineCache.delete(`/offline-book-marker/${bookId}`);
                    }

                    if (event.ports && event.ports[0]) {
                        event.ports[0].postMessage({
                            type: 'BOOK_CACHE_STATUS',
                            bookId,
                            isCached,
                            evicted: !isCached // Signal if cache was evicted
                        });
                    }
                } else {
                    // No marker found
                    if (event.ports && event.ports[0]) {
                        event.ports[0].postMessage({
                            type: 'BOOK_CACHE_STATUS',
                            bookId,
                            isCached: false
                        });
                    }
                }
            } catch (error) {
                if (event.ports && event.ports[0]) {
                    event.ports[0].postMessage({
                        type: 'BOOK_CACHE_STATUS',
                        bookId,
                        isCached: false
                    });
                }
            }
        }

        // Get list of all offline-saved books (with verification)
        if (event.data && event.data.type === 'GET_OFFLINE_BOOKS') {
            try {
                const offlineCache = await caches.open('offline-books-cache');
                const bookDataCache = await caches.open('book-data-cache');
                const chaptersCache = await caches.open('chapters-cache');
                const requests = await offlineCache.keys();

                // Extract book IDs from marker URLs and verify content still exists
                const offlineBookIds = [];
                const evictedBookIds = [];

                for (const request of requests) {
                    const match = request.url.match(/\/offline-book-marker\/(\d+)/);
                    if (match) {
                        const bookId = parseInt(match[1]);

                        // Verify actual content is cached
                        const bookData = await bookDataCache.match(`/api/books/${bookId}`);
                        const chaptersList = await chaptersCache.match(`/api/books/${bookId}/chapters`);

                        if (bookData && chaptersList) {
                            // Content exists - book is truly cached
                            offlineBookIds.push(bookId);
                        } else {
                            // Marker exists but content is gone - cache was evicted
                            console.warn(`Book ${bookId} marker found but content evicted`);
                            evictedBookIds.push(bookId);
                            // Clean up stale marker
                            await offlineCache.delete(`/offline-book-marker/${bookId}`);
                        }
                    }
                }

                if (event.ports && event.ports[0]) {
                    event.ports[0].postMessage({
                        type: 'OFFLINE_BOOKS_LIST',
                        bookIds: offlineBookIds,
                        evictedBookIds: evictedBookIds // Report which books were evicted
                    });
                }
            } catch (error) {
                if (event.ports && event.ports[0]) {
                    event.ports[0].postMessage({
                        type: 'OFFLINE_BOOKS_LIST',
                        bookIds: [],
                        evictedBookIds: []
                    });
                }
            }
        }
    });

    // Helper function to determine cache name for URL
    function getCacheNameForUrl(url) {
        if (url.includes('/summary/')) return 'summaries-cache';
        if (url.includes('/chapters/')) return 'chapters-cache';
        if (url.includes('/books/')) return 'book-data-cache';
        return 'pages-cache';
    }

    console.log('Service Worker setup complete');
} else {
    console.error('Workbox failed to load');
}
