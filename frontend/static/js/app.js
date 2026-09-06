// Summra Frontend JavaScript - Redesigned
//
// ARCHITECTURE: Centralized Section Management
// ============================================
// All page sections are managed through a single source of truth (this.ALL_SECTIONS).
// To show a page, call this.showOnlySections('section-id') which automatically hides all others.
//
// Adding a new page:
// 1. Add the section ID to this.ALL_SECTIONS array in constructor
// 2. Create a show*() function that calls this.showOnlySections('your-section-id')
// 3. Add routing logic to handleRoute()
//
// This prevents bugs where sections from one page leak into another page.
//
// URL PREFIX: window.APP_BASE_PATH (injected by the base template from Flask's
// request.script_root) lets this app be reverse-proxied under a path prefix
// (e.g. /summrabook) without any other code changes. summraBasePath()/
// withBasePath() are defined in route_utils.js (loaded before this file, and
// before components/BlogIndex.js and components/BlogPost.js, which also need
// withBasePath) rather than duplicated here.
//
// MODULE SPLIT (2026-09 refactor, in progress): this file is loaded as
// `<script type="module">` (see index.html) so it can `import` sibling
// modules — subsystems moved out of the SummraApp class are plain objects
// of methods, merged onto SummraApp.prototype via Object.assign after the
// class body. Every method still references `this.*` exactly as before;
// only their source location moved. The production build bundles these
// back into one file (`esbuild --bundle`, see package.json) so app.min.js
// stays a single <script> with no import/export left in it.
import { paginationMixin } from './pagination.js';
import { settingsMixin } from './settings.js';
import { breadcrumbsMixin } from './breadcrumbs.js';
import { offlineMixin } from './offline.js';
import { audioMixin } from './audio.js';
import { readerMixin } from './reader.js';

class SummraApp {
    constructor() {
        this.apiBase = withBasePath('/api');
        this.currentBook = null;
        this.currentCategory = null;
        this.currentSummaryType = null;
        this.allBooks = [];
        this.booksLoaded = false;
        this.chapters = [];
        this.currentChapter = null;
        this.currentView = 'home'; // Track current view: 'home', 'book', 'category', 'all-categories', 'all-books'
        this.currentPlayback = {
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null
        };
        // Store scroll positions for each page
        this.scrollPositions = {};
        this.currentPage = 'home'; // Track current page for scroll saving
        // Cache category data to prevent re-fetching
        this.categoryCache = {}; // { categoryId: { category: {...}, books: [...] } }
        // Cache shuffled book orders for carousels
        this.carouselOrderCache = {}; // { carouselId: [shuffled books array] }
        // Track where user came from for context-aware breadcrumbs
        this.originCategory = null; // Store category when book is selected from category page
        this.originDiscover = false; // Track if book is selected from Discover page
        this.originAuthor = null; // Store author when book is selected from author page
        // Track short summary expanded state
        this.conciseSummaryExpanded = false;

        // Pagination state for chapter reading
        this.pagination = {
            enabled: true, // Pagination is enabled by default
            currentPage: 0,
            totalPages: 0,
            pages: [], // Array of page content
            containerHeight: 0,
            isNavigating: false, // Prevent rapid page changes
            touchStartX: 0,
            touchStartY: 0,
            currentViewMode: 'original', // Track current view mode for pagination
            buttonTimers: [] // Store timer references for cleanup
        };

        // Centralized list of ALL content sections (single source of truth)
        // When adding a new page/section, add its ID here once
        this.ALL_SECTIONS = [
            'hero-section',
            'summary-section',
            'medium-detail-section',
            'chapter-detail-section',
            'category-detail-section',
            'all-categories-section',
            'author-detail-section',
            'discover-section',
            'blog-index-section',
            'blog-post-section'
        ];

        this.init();
    }

    async init() {
        // Don't load all books/categories upfront - use lazy loading instead
        // Only load when needed by specific pages

        this.setupEventListeners();
        this.setupPersistentPlayer();
        this.setupRouting();
        this.configureMarked();
        this.setupReadingSettings();
        this.setupLightbox();
        this.setupAdminFeatures();
        this.loadReadingPreferences();
        this.registerServiceWorker();
        this.setupInstallPrompt();
        this.setupPagination();
    }

    registerServiceWorker() {
        // Register service worker for PWA functionality
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register(withBasePath('/service-worker.js'))
                    .then((registration) => {
                        console.log('✅ Service Worker registered successfully:', registration.scope);

                        // Check for updates periodically
                        registration.addEventListener('updatefound', () => {
                            const newWorker = registration.installing;
                            console.log('🔄 Service Worker update found');

                            newWorker.addEventListener('statechange', () => {
                                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                    // New service worker available, show update notification
                                    console.log('✨ New content available! Refresh to update.');
                                    // TODO: Show user-friendly update notification
                                }
                            });
                        });

                        // Request persistent storage (critical for iOS PWA)
                        // This helps prevent iOS from clearing cache after inactivity
                        this.requestPersistentStorage();
                    })
                    .catch((error) => {
                        console.log('❌ Service Worker registration failed:', error);
                    });
            });
        } else {
            console.log('⚠️  Service Workers not supported in this browser');
        }
    }

    async requestPersistentStorage() {
        // Request persistent storage to prevent iOS from clearing cache
        // iOS 17+ supports this API and may grant persistence for home screen PWAs
        if (navigator.storage && navigator.storage.persist) {
            try {
                const isPersisted = await navigator.storage.persist();
                if (isPersisted) {
                    console.log('✅ Persistent storage granted - cache protected from eviction');
                } else {
                    console.log('⚠️  Persistent storage denied - cache may be cleared after inactivity');
                    console.log('💡 Tip: Add this app to your home screen for better persistence');
                }

                // Check current persistence status
                const persisted = await navigator.storage.persisted();
                console.log('Storage persistence status:', persisted ? 'PERSISTENT' : 'BEST-EFFORT');

                // Check storage quota (helpful for debugging iOS limits)
                if (navigator.storage.estimate) {
                    const estimate = await navigator.storage.estimate();
                    const usedMB = (estimate.usage / (1024 * 1024)).toFixed(2);
                    const quotaMB = (estimate.quota / (1024 * 1024)).toFixed(2);
                    console.log(`Storage used: ${usedMB} MB / ${quotaMB} MB (${((estimate.usage / estimate.quota) * 100).toFixed(1)}%)`);
                }

                // Run periodic cache health check
                this.performCacheHealthCheck();
            } catch (error) {
                console.log('Storage API error:', error);
            }
        } else {
            console.log('⚠️  Storage API not supported - persistence not available');
        }
    }

    async performCacheHealthCheck() {
        // Verify cached books still have their content
        // This detects iOS cache eviction and cleans up stale markers
        try {
            const offlineBooks = await this.getOfflineBooks();

            if (offlineBooks.evictedBookIds && offlineBooks.evictedBookIds.length > 0) {
                console.warn(`⚠️  Cache eviction detected! ${offlineBooks.evictedBookIds.length} book(s) lost:`, offlineBooks.evictedBookIds);
                console.log('💡 Books need to be re-downloaded for offline access');

                // Store eviction info for user notification
                localStorage.setItem('summra_cache_evicted', JSON.stringify({
                    bookIds: offlineBooks.evictedBookIds,
                    detectedAt: new Date().toISOString()
                }));
            } else if (offlineBooks.bookIds && offlineBooks.bookIds.length > 0) {
                console.log(`✅ Cache health check passed - ${offlineBooks.bookIds.length} book(s) still cached`);
            }
        } catch (error) {
            console.error('Cache health check failed:', error);
        }
    }

    setupInstallPrompt() {
        // Detect iOS Safari
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        const isInStandaloneMode = ('standalone' in window.navigator) && window.navigator.standalone;

        // Check if already installed or dismissed
        const installBannerDismissed = localStorage.getItem('installBannerDismissed');

        // Show iOS install banner if:
        // 1. User is on iOS
        // 2. Not already in standalone mode (not installed)
        // 3. Haven't dismissed the banner before
        if (isIOS && !isInStandaloneMode && !installBannerDismissed) {
            setTimeout(() => {
                const banner = document.getElementById('ios-install-banner');
                if (banner) {
                    banner.classList.remove('hidden');
                }
            }, 2000); // Show after 2 seconds
        }

        // Handle Android Chrome install prompt
        let deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {
            // Prevent the mini-infobar from appearing on mobile
            e.preventDefault();
            // Stash the event so it can be triggered later
            deferredPrompt = e;

            // Show custom install button (we can implement this later)
            console.log('💡 Install prompt available');
        });
    }

    setupRouting() {
        // Handle popstate for browser back/forward buttons
        window.addEventListener('popstate', () => {
            this.handleRoute();
        });

        // Intercept all link clicks for client-side routing
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href^="/"]');
            if (!link) return;

            const href = link.getAttribute('href');

            // Skip external links and download links
            if (link.hasAttribute('target') || link.hasAttribute('download')) {
                return;
            }

            // Handle clean URLs
            if (href.startsWith('/') && !href.startsWith(withBasePath('/api/')) && !href.startsWith(withBasePath('/static/'))) {
                e.preventDefault();
                window.history.pushState(null, '', href);
                this.handleRoute();
            }
        });

        // Handle the initial route immediately
        this.handleRoute();
    }

    async handleRoute() {
        // Use pathname for routing (clean URLs), stripped of any deploy-time base path
        const path = currentAppPath();

        // Home page
        if (!path || path === '/') {
            this.showHomeSection();
            return;
        }

        // Parse routes (shared with buildBreadcrumbs() via parseAppRoute —
        // see route_utils.js):
        // /books/{slug} - Book detail
        // /books/{slug}/summary - Medium summary detail
        // /books/{slug}/chapters/{num} - Chapter detail
        // /categories/{id} - Category detail
        // /categories - All categories view
        // /books - All books grid view
        // /discover - Discover page by difficulty
        // /authors/{name} - Author detail
        // /blog - Blog index
        // /blog/{slug} - Blog post
        const {
            bookMatch, mediumMatch, chapterMatch, categoryMatch, categoriesMatch,
            allBooksMatch, discoverMatch, authorMatch, blogMatch, blogPostMatch
        } = parseAppRoute(path);

        // Routes that don't need books data - proceed immediately
        if (blogPostMatch) {
            const slug = blogPostMatch[1];
            await this.showBlogPost(slug, true);
        } else if (blogMatch) {
            await this.showBlogIndex(true);
        } else if (discoverMatch) {
            await this.showDiscoverPage(true);
        }
        // Routes that need books data - load books first
        else {
            // Ensure books are loaded for book-related routes
            await this.ensureBooksLoaded();

            if (authorMatch) {
                const authorName = decodeURIComponent(authorMatch[1]);
                await this.showAuthorDetail(authorName, true);
            } else if (chapterMatch) {
                const bookSlug = chapterMatch[1];
                const chapterNum = parseInt(chapterMatch[2]);
                const book = this.allBooks.find(b => (b.slug || this.slugify(b.title)) === bookSlug);
                if (book) {
                    // Set current book and load chapters if not already loaded
                    this.currentBook = book;
                    if (this.chapters.length === 0 || this.chapters[0]?.book_id !== book.id) {
                        await this.loadChapters();
                    }
                    await this.showChapterDetail(book, chapterNum, true);
                }
            } else if (mediumMatch) {
                const bookSlug = mediumMatch[1];
                const book = this.allBooks.find(b => (b.slug || this.slugify(b.title)) === bookSlug);
                if (book) {
                    await this.showMediumDetail(book, true);
                }
            } else if (bookMatch) {
                const bookSlug = bookMatch[1];
                const book = this.allBooks.find(b => (b.slug || this.slugify(b.title)) === bookSlug);
                if (book) {
                    await this.selectBook(book, true);
                }
            } else if (categoryMatch) {
                const categoryId = parseInt(categoryMatch[1]);
                await this.showCategoryDetail(categoryId, true);
            } else if (categoriesMatch) {
                await this.showAllCategories(true);
            } else if (allBooksMatch) {
                await this.showAllBooksGrid(true);
            }
        }
    }

    async waitForBooks() {
        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                if (this.booksLoaded) {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 100);
        });
    }

    slugify(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/--+/g, '-')
            .trim();
    }

    normalizeBookTitle(title) {
        /**
         * Normalize book title for comparison:
         * - Convert to lowercase
         * - Remove punctuation and special characters
         * - Remove common articles (a, an, the)
         * - Collapse whitespace
         */
        return title
            .toLowerCase()
            .replace(/[^\w\s]/g, '') // Remove punctuation
            .replace(/\b(a|an|the)\b/g, '') // Remove articles
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();
    }

    fuzzyMatchTitles(title1, title2) {
        /**
         * Fuzzy match two normalized book titles
         * Returns true if titles are similar enough to be considered the same book
         */
        // Exact match after normalization
        if (title1 === title2) {
            return true;
        }

        // Check if one title contains the other (handles "The Count of Monte Cristo" vs "Count of Monte Cristo")
        if (title1.includes(title2) || title2.includes(title1)) {
            return true;
        }

        // Calculate similarity ratio (simple character overlap)
        const longer = title1.length > title2.length ? title1 : title2;
        const shorter = title1.length > title2.length ? title2 : title1;

        // If the shorter title is contained in the longer one with very minor differences
        const threshold = 0.85; // 85% similarity
        const similarity = this.calculateStringSimilarity(title1, title2);

        return similarity >= threshold;
    }

    calculateStringSimilarity(str1, str2) {
        /**
         * Calculate similarity between two strings using Levenshtein distance
         * Returns a value between 0 and 1 (1 = identical)
         */
        const longer = str1.length > str2.length ? str1 : str2;
        const shorter = str1.length > str2.length ? str2 : str1;

        if (longer.length === 0) {
            return 1.0;
        }

        const editDistance = this.levenshteinDistance(str1, str2);
        return (longer.length - editDistance) / longer.length;
    }

    levenshteinDistance(str1, str2) {
        /**
         * Calculate Levenshtein distance between two strings
         * (minimum number of single-character edits needed to change one string into the other)
         */
        const matrix = [];

        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }

        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }

        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1, // substitution
                        matrix[i][j - 1] + 1,     // insertion
                        matrix[i - 1][j] + 1      // deletion
                    );
                }
            }
        }

        return matrix[str2.length][str1.length];
    }

    /**
     * Hide all sections except the ones specified
     * This is the SINGLE METHOD to control section visibility across the entire app
     * @param {string|string[]} sectionsToShow - Section ID(s) to keep visible (all others will be hidden)
     */
    showOnlySections(sectionsToShow) {
        // Convert single string to array for uniform processing
        const showArray = Array.isArray(sectionsToShow) ? sectionsToShow : [sectionsToShow];

        // Clear pagination when leaving chapter page
        if (!showArray.includes('chapter-detail-section')) {
            this.clearPagination();
        }

        // Hide the footer on chapter pages (focused reading view); show it elsewhere.
        // Mirrors the server-side Jinja gate in index.html so SPA navigation matches.
        const footer = document.querySelector('footer.footer');
        if (footer) {
            const onChapter = showArray.includes('chapter-detail-section');
            footer.classList.toggle('hidden', onChapter);
        }

        // Toggle body class for chapter/medium reading pages. CSS uses this to
        // hide the site .header deterministically (replaces a body:has() rule
        // whose WebKit re-evaluation can lag a frame on iOS, leaking the site
        // nav over the chapter text after pushState navigation).
        const onReadingPage = showArray.includes('chapter-detail-section') ||
                              showArray.includes('medium-detail-section');
        document.body.classList.toggle('on-chapter-page', onReadingPage);

        // Only modify sections if they're not already in the correct state
        // This prevents flash when server-side rendered page is already showing correct section
        this.ALL_SECTIONS.forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) {
                const shouldBeVisible = showArray.includes(sectionId);
                const isCurrentlyVisible = !section.classList.contains('hidden');

                // Only modify if state needs to change
                if (shouldBeVisible && !isCurrentlyVisible) {
                    section.classList.remove('hidden');
                } else if (!shouldBeVisible && isCurrentlyVisible) {
                    section.classList.add('hidden');
                }
            }
        });
    }

    /**
     * Update document title for client-side navigation
     * @param {string} title - The new page title
     */
    updatePageTitle(title) {
        document.title = title;
    }

    saveScrollPosition() {
        this.scrollPositions[this.currentPage] = window.scrollY;
        console.log(`[Scroll] Saved scroll position for ${this.currentPage}: ${window.scrollY}`);
    }

    restoreScrollPosition(pageKey) {
        const position = this.scrollPositions[pageKey] || 0;
        console.log(`[Scroll] Restoring scroll position for ${pageKey}: ${position}`);
        // Use requestAnimationFrame to ensure DOM is fully rendered
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                window.scrollTo(0, position);
                console.log(`[Scroll] Actually scrolled to: ${position}, current scroll: ${window.scrollY}`);
            });
        });
    }

    setCurrentPage(pageKey) {
        this.currentPage = pageKey;
    }

    /**
     * Shared tail for page-controller methods (showCategoryDetail,
     * showAllCategories, showAllBooksGrid, showBlogIndex, showBlogPost):
     * update breadcrumbs, restore scroll (or jump to top), then set the page
     * title. The three steps are independent (verified: none reads state the
     * others set), so this fixed order is safe regardless of a given page's
     * original statement order.
     * @param {string} breadcrumbKey - passed to updateBreadcrumbs()
     * @param {string} scrollPageKey - passed to restoreScrollPosition() when restoreScroll is true
     * @param {boolean} restoreScroll - restore saved position vs. scroll to top
     * @param {string|null} title - passed to updatePageTitle(); skipped if falsy
     */
    finishPageTransition(breadcrumbKey, scrollPageKey, restoreScroll, title) {
        this.updateBreadcrumbs(breadcrumbKey);

        if (restoreScroll) {
            this.restoreScrollPosition(scrollPageKey);
        } else {
            window.scrollTo(0, 0);
        }

        if (title) {
            this.updatePageTitle(title);
        }
    }

    updateURL(book, page = null) {
        // Use slug from backend if available, fallback to generating from title
        const slug = book.slug || this.slugify(book.title);
        let newPath = withBasePath(`/books/${slug}`);

        if (page === 'summary') {
            newPath = withBasePath(`/books/${slug}/summary`);
        } else if (typeof page === 'number') {
            newPath = withBasePath(`/books/${slug}/chapters/${page}`);
        }

        if (window.location.pathname !== newPath) {
            window.history.pushState(null, '', newPath);
        }
    }

    configureMarked() {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        }
    }

    setupEventListeners() {
        // Note: Back buttons have been replaced with breadcrumb navigation
        // Breadcrumbs are updated via updateBreadcrumbs() in each view method

        // #header-home-link ("<a href="{{ base_path }}/">") needs no listener
        // of its own — setupRouting()'s delegated `a[href^="/"]` click handler
        // already intercepts it. A dedicated handler used to live here too,
        // double-firing showHomeSection() on every click (both handlers
        // matched the same link) and racing two concurrent async calls —
        // occasionally observable as the hero section staying hidden after
        // navigating home. Removed rather than kept in sync with the
        // delegated handler's logic.

        // Setup iOS install banner close button
        const iosBannerClose = document.getElementById('ios-banner-close');
        if (iosBannerClose) {
            iosBannerClose.addEventListener('click', () => {
                const banner = document.getElementById('ios-install-banner');
                if (banner) {
                    banner.classList.add('hidden');
                    // Remember user dismissed the banner
                    localStorage.setItem('installBannerDismissed', 'true');
                }
            });
        }

        // Setup summary tab switching
        this.setupSummaryTabs();

        // Setup reading guide tab switching
        this.setupGuideTabs();

        // Track user interaction to help iOS recognize active usage
        // This helps prevent cache eviction on iOS by showing the app is actively used
        this.setupIOSInteractionTracking();
    }

    setupIOSInteractionTracking() {
        // Track user interactions to signal app is actively used
        // iOS uses interaction history to determine if PWA should keep its cache
        const updateLastInteraction = () => {
            localStorage.setItem('summra_last_interaction', new Date().toISOString());
        };

        // Track various user interactions
        const interactionEvents = ['click', 'scroll', 'touchstart', 'keydown'];
        interactionEvents.forEach(eventType => {
            document.addEventListener(eventType, updateLastInteraction, { passive: true });
        });

        // Log interaction tracking start (helpful for debugging)
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        if (isIOS) {
            console.log('📱 iOS interaction tracking enabled - helps prevent cache eviction');
        }
    }

    setupGuideTabs() {
        const readingGuideTabs = document.querySelectorAll('.reading-guide-tab');
        readingGuideTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetTab = e.target.dataset.readingTab;

                // Remove active class from all reading guide tabs and contents
                document.querySelectorAll('.reading-guide-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.reading-guide-tab-content').forEach(c => c.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                e.target.classList.add('active');
                const targetContent = document.getElementById(`reading-tab-${targetTab}`);
                if (targetContent) {
                    targetContent.classList.add('active');
                }
            });
        });
    }

    setupSummaryTabs() {
        const tabs = document.querySelectorAll('.summary-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetTab = e.target.dataset.tab;

                // If switching to full summary and short summary is expanded, collapse it
                if (targetTab === '2000-word' && this.conciseSummaryExpanded) {
                    this.collapseConciseSummary();
                }

                // Remove active class from all tabs and contents
                document.querySelectorAll('.summary-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.summary-tab-content').forEach(c => c.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                e.target.classList.add('active');
                const targetContent = document.getElementById(`tab-${targetTab}`);
                if (targetContent) {
                    targetContent.classList.add('active');
                }

                // Update TTS button for active tab
                this.updateSummaryTTSButton();
            });
        });
    }

    async loadCategories() {
        try {
            const response = await fetch(`${this.apiBase}/categories`);
            const data = await response.json();

            if (data.success && data.categories.length > 0) {
                // Load books for each category and display
                this.displayCategories(data.categories);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
            // Categories are optional, so don't show error to user
        }
    }

    async displayCategories(categories) {
        const categoriesContainer = document.getElementById('categories-container');
        if (!categoriesContainer) {
            // Categories container not present on this page (e.g., home page)
            return;
        }
        categoriesContainer.innerHTML = '';

        // Use already-loaded books data to filter by category client-side
        // This avoids making 50+ API calls for each category
        const categoriesWithBooks = categories.map(category => {
            // Filter all books to find those in this category
            const booksInCategory = this.allBooks.filter(book =>
                book.categories && book.categories.some(cat => cat.id === category.id)
            );

            // Cache the result for later use
            if (booksInCategory.length > 0) {
                this.categoryCache[category.id] = {
                    category,
                    books: booksInCategory
                };
            }

            return {
                category,
                books: booksInCategory,
                bookCount: booksInCategory.length
            };
        });

        // Filter out categories with no books and sort by book count
        const validCategories = categoriesWithBooks
            .filter(item => item.bookCount > 0)
            .sort((a, b) => b.bookCount - a.bookCount);

        // Show top 10 categories
        const topCategories = validCategories.slice(0, 10);

        // Render carousels using cached data
        for (const item of topCategories) {
            this.renderCategoryCarousel(item.category, item.books);
        }

        // Add "All Books" carousel at the end
        this.renderCategoryCarousel(
            { id: 'all', name: 'All Books' },
            this.allBooks
        );
    }

    renderCategoryCarousel(category, books, containerIdOverride = null) {
        const categoriesContainer = document.getElementById(containerIdOverride || 'categories-container');

        const carouselSection = document.createElement('div');
        carouselSection.className = 'category-carousel';

        const header = document.createElement('div');
        header.className = 'category-header';

        // Check if this is for the discover page (no View All links for discover carousels)
        const isDiscoverPage = containerIdOverride === 'discover-carousels-container';

        // Add View All link (except for "All Books" carousel, discover page, or popular carousel)
        const viewAllLink = !isDiscoverPage && category.id !== 'all' && category.id !== 'popular'
            ? `<a href="${withBasePath(`/categories/${category.id}`)}" class="view-all-link">View All →</a>`
            : category.id === 'all' && !isDiscoverPage
                ? `<a href="${withBasePath('/books')}" class="view-all-link">View All →</a>`
                : '';

        header.innerHTML = `
            <h2 class="category-title">${this.escapeHtml(category.name)}</h2>
            ${viewAllLink}
        `;

        const carousel = document.createElement('div');
        carousel.className = 'carousel-container';

        // Add navigation buttons
        const leftBtn = document.createElement('button');
        leftBtn.className = 'carousel-nav-btn left';
        leftBtn.innerHTML = '‹';
        leftBtn.disabled = true;  // Start disabled (at beginning)

        const rightBtn = document.createElement('button');
        rightBtn.className = 'carousel-nav-btn right';
        rightBtn.innerHTML = '›';
        rightBtn.disabled = false;  // Start enabled (can scroll right)

        const scrollContainer = document.createElement('div');
        scrollContainer.className = 'carousel-scroll';

        // Use cached shuffled order or create new one
        const carouselId = `${category.id}_${containerIdOverride || 'default'}`;
        let shuffledBooks = this.carouselOrderCache[carouselId];

        if (!shuffledBooks) {
            // Randomize book order and cache it
            shuffledBooks = [...books].sort(() => Math.random() - 0.5);
            this.carouselOrderCache[carouselId] = shuffledBooks;
        }

        shuffledBooks.forEach(book => {
            const bookCard = document.createElement('div');
            bookCard.className = 'carousel-book-card';

            const coverImageHtml = book.cover_image_url
                ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, 'carousel-book-cover')
                : '';

            bookCard.innerHTML = `
                ${coverImageHtml}
                <h4 class="carousel-book-title">${this.escapeHtml(book.title)}</h4>
                <p class="carousel-book-author">${this.escapeHtml(book.author)}</p>
            `;

            bookCard.addEventListener('click', () => this.selectBook(book));
            scrollContainer.appendChild(bookCard);
        });

        // Carousel navigation logic
        const scrollAmount = 220; // Width of one card + gap

        leftBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: -scrollAmount * 3, behavior: 'smooth' });
        });

        rightBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: scrollAmount * 3, behavior: 'smooth' });
        });

        // Update button states on scroll
        const updateButtonStates = () => {
            leftBtn.disabled = scrollContainer.scrollLeft <= 0;
            rightBtn.disabled = scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 1;
        };

        scrollContainer.addEventListener('scroll', updateButtonStates);

        // Wait for DOM to render before checking initial state
        setTimeout(() => updateButtonStates(), 0);

        carousel.appendChild(leftBtn);
        carousel.appendChild(scrollContainer);
        carousel.appendChild(rightBtn);
        carouselSection.appendChild(header);
        carouselSection.appendChild(carousel);
        categoriesContainer.appendChild(carouselSection);
    }

    renderTop10Carousel() {
        // Top 10 most downloaded books from Project Gutenberg (by Gutenberg ID)
        // Using popular books we have in our database
        const top10GutenbergIds = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345];

        // Find books in our database that match these IDs
        const top10Books = [];
        top10GutenbergIds.forEach((gutenbergId, index) => {
            const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
            if (book) {
                top10Books.push({ book, rank: index + 1 });
            }
        });

        const scrollContainer = document.getElementById('top-10-scroll');
        if (!scrollContainer || top10Books.length === 0) return;

        // Clear skeleton loading cards
        scrollContainer.innerHTML = '';

        // Create book cards with rank overlays
        top10Books.forEach(({ book, rank }) => {
            const bookCard = document.createElement('div');
            bookCard.className = 'top-10-book-card';

            const cardInner = document.createElement('div');
            cardInner.className = 'top-10-book-card-inner';

            const coverImageHtml = book.cover_image_url
                ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, '')
                : '';

            cardInner.innerHTML = `
                ${coverImageHtml}
                <div class="top-10-rank-overlay">
                    <div class="top-10-rank-number">${rank}</div>
                </div>
            `;

            bookCard.appendChild(cardInner);
            bookCard.addEventListener('click', () => this.selectBook(book));
            scrollContainer.appendChild(bookCard);
        });

        // Setup carousel navigation
        const leftBtn = document.getElementById('top-10-nav-left');
        const rightBtn = document.getElementById('top-10-nav-right');

        const scrollAmount = 170; // Width of card + gap

        leftBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: -scrollAmount * 3, behavior: 'smooth' });
        });

        rightBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: scrollAmount * 3, behavior: 'smooth' });
        });

        // Update button states on scroll
        const updateButtonStates = () => {
            leftBtn.disabled = scrollContainer.scrollLeft <= 0;
            rightBtn.disabled = scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 1;
        };

        scrollContainer.addEventListener('scroll', updateButtonStates);
        setTimeout(() => updateButtonStates(), 100);
    }

    renderTop10AsStandardCarousel(containerId, title = 'Popular') {
        // Top 10 most downloaded books from Project Gutenberg (by Gutenberg ID)
        const top10GutenbergIds = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345];

        // Find books in our database that match these IDs
        const top10Books = [];
        top10GutenbergIds.forEach((gutenbergId) => {
            const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
            if (book) {
                top10Books.push(book);
            }
        });

        if (top10Books.length === 0) return;

        // Use the standard category carousel rendering
        const container = document.getElementById(containerId);
        if (!container) return;

        // Render using the same method as other category carousels
        this.renderCategoryCarousel(
            { id: 'popular', name: title },
            top10Books,
            containerId
        );
    }

    renderTop10CarouselInContainer(containerId, title = 'Most Popular Classics') {
        // Top 10 most downloaded books from Project Gutenberg (by Gutenberg ID)
        const top10GutenbergIds = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345];

        // Find books in our database that match these IDs
        const top10Books = [];
        top10GutenbergIds.forEach((gutenbergId, index) => {
            const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
            if (book) {
                top10Books.push({ book, rank: index + 1 });
            }
        });

        const container = document.getElementById(containerId);
        if (!container || top10Books.length === 0) return;

        // Create carousel section with header
        const carouselSection = document.createElement('div');
        carouselSection.className = 'category-carousel';

        const header = document.createElement('div');
        header.className = 'category-header';
        header.innerHTML = `<h2 class="category-title">${this.escapeHtml(title)}</h2>`;

        const carouselContainer = document.createElement('div');
        carouselContainer.className = 'carousel-container top-10-carousel';

        // Add navigation buttons
        const leftBtn = document.createElement('button');
        leftBtn.className = 'carousel-nav-btn left';
        leftBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"></path></svg>';
        leftBtn.disabled = true;

        const rightBtn = document.createElement('button');
        rightBtn.className = 'carousel-nav-btn right';
        rightBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"></path></svg>';

        const scrollContainer = document.createElement('div');
        scrollContainer.className = 'carousel-scroll';

        // Create book cards with rank overlays
        top10Books.forEach(({ book, rank }) => {
            const bookCard = document.createElement('div');
            bookCard.className = 'top-10-book-card';

            const cardInner = document.createElement('div');
            cardInner.className = 'top-10-book-card-inner';

            const coverImageHtml = book.cover_image_url
                ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, '')
                : '';

            cardInner.innerHTML = `
                ${coverImageHtml}
                <div class="top-10-rank-overlay">
                    <div class="top-10-rank-number">${rank}</div>
                </div>
            `;

            bookCard.appendChild(cardInner);
            bookCard.addEventListener('click', () => this.selectBook(book));
            scrollContainer.appendChild(bookCard);
        });

        // Setup carousel navigation
        const scrollAmount = 170; // Width of card + gap

        leftBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: -scrollAmount * 3, behavior: 'smooth' });
        });

        rightBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: scrollAmount * 3, behavior: 'smooth' });
        });

        // Update button states on scroll
        const updateButtonStates = () => {
            leftBtn.disabled = scrollContainer.scrollLeft <= 0;
            rightBtn.disabled = scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 1;
        };

        scrollContainer.addEventListener('scroll', updateButtonStates);
        setTimeout(() => updateButtonStates(), 100);

        // Assemble carousel
        carouselContainer.appendChild(leftBtn);
        carouselContainer.appendChild(scrollContainer);
        carouselContainer.appendChild(rightBtn);
        carouselSection.appendChild(header);
        carouselSection.appendChild(carouselContainer);
        container.appendChild(carouselSection);
    }

    async loadBooks() {
        // Skip if already loaded
        if (this.booksLoaded) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/books`);
            const data = await response.json();

            if (data.success && data.books.length > 0) {
                this.allBooks = data.books;
                this.booksLoaded = true;
            } else {
                this.booksLoaded = true;
                console.warn('No books found in database');
            }
        } catch (error) {
            console.error('Error loading books:', error);
            this.booksLoaded = true;
        }
    }

    async ensureBooksLoaded() {
        if (!this.booksLoaded) {
            await this.loadBooks();
        }
    }

    async selectBook(book, restoreScroll = false) {
        // Track origin for context-aware breadcrumbs BEFORE changing view
        // If we're currently viewing a category, store it as the origin
        if (this.currentView === 'category' && this.currentCategory) {
            this.originCategory = {
                id: this.currentCategory.id,
                name: this.currentCategory.name
            };
            this.originDiscover = false;
            this.originAuthor = null;
        }
        // If navigating from Discover page, set origin flag
        else if (this.currentView === 'discover') {
            this.originCategory = null;
            this.originDiscover = true;
            this.originAuthor = null;
        }
        // If navigating from Author page, store author as origin
        else if (this.currentView === 'author' && this.currentAuthor) {
            this.originCategory = null;
            this.originDiscover = false;
            this.originAuthor = {
                name: this.currentAuthor.name,
                slug: this.slugify(this.currentAuthor.name)
            };
        }
        // If navigating from All Books or home, clear origin
        else if (this.currentView === 'all-books' || this.currentView === 'home') {
            this.originCategory = null;
            this.originDiscover = false;
            this.originAuthor = null;
        }
        // Otherwise, keep the existing origin (e.g., when navigating within book pages)

        this.currentBook = book;
        this.currentView = 'book';

        // Reset short summary expanded state when switching books
        this.conciseSummaryExpanded = false;

        // Save current scroll position
        this.saveScrollPosition();

        // Update book info
        const bookTitle = document.getElementById('book-title');
        const bookAuthor = document.getElementById('book-author');

        if (bookTitle) bookTitle.textContent = book.title;
        if (bookAuthor) {
            const authorSlug = this.slugify(book.author);
            bookAuthor.innerHTML = `by <a href="${withBasePath(`/authors/${authorSlug}`)}" class="author-link">${this.escapeHtml(book.author)}</a>`;
        }

        // Fetch full book data to get metadata (about_text, relevance_now, author info)
        this.loadBookMetadata(book.id);

        // Handle book cover - check for both <img> and <picture> elements
        let bookCoverContainer = document.getElementById('book-info-cover');

        // If we replaced it with <picture> before, the img won't have the ID anymore
        // So look for the picture element inside the parent
        if (!bookCoverContainer) {
            const parent = document.querySelector('.book-detail-header');
            bookCoverContainer = parent?.querySelector('picture') || parent?.querySelector('img');
        }

        if (bookCoverContainer && book.cover_image_url) {
            // Prepend /static/ to the path if it starts with /covers/ or covers/ (for consistency with other pages)
            let fullImageUrl = book.cover_image_url;
            if (book.cover_image_url.startsWith('/covers/')) {
                fullImageUrl = '/static' + book.cover_image_url;
            } else if (book.cover_image_url.startsWith('covers/')) {
                fullImageUrl = '/static/' + book.cover_image_url;
            }
            fullImageUrl = withBasePath(fullImageUrl);

            // Get base URL without extension for WebP/JPG support
            const urlWithoutExt = fullImageUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');

            // If it's still the original <img> element, replace with <picture>
            if (bookCoverContainer.tagName === 'IMG') {
                const pictureHtml = `
                    <picture id="book-info-cover">
                        <source srcset="${this.escapeHtml(urlWithoutExt + '.webp')}" type="image/webp">
                        <img src="${this.escapeHtml(urlWithoutExt + '.jpg')}"
                             alt="${this.escapeHtml(book.title)} cover"
                             class="book-detail-cover">
                    </picture>
                `;
                bookCoverContainer.outerHTML = pictureHtml;
            } else {
                // Already a <picture> element, just update the sources
                const source = bookCoverContainer.querySelector('source');
                const img = bookCoverContainer.querySelector('img');

                if (source) {
                    source.srcset = urlWithoutExt + '.webp';
                }
                if (img) {
                    img.src = urlWithoutExt + '.jpg';
                    img.alt = `${book.title} cover`;
                }
            }

            bookCoverContainer = document.getElementById('book-info-cover');
            if (bookCoverContainer) {
                bookCoverContainer.classList.remove('hidden');
            }
        } else if (bookCoverContainer) {
            bookCoverContainer.classList.add('hidden');
        }

        // Show book detail section (handles all section visibility)
        this.showBookDetail(restoreScroll);

        // Render breadcrumbs eagerly here — after the section visibility
        // transition (so #breadcrumb-nav-book's parent is no longer
        // display:none) but before any await (so the breadcrumb is filled in
        // synchronously and the user never sees a 0-height gap between the
        // outgoing page's breadcrumb being hidden and this page's being
        // rendered — the "breadcrumb snap-in" regression).
        // The breadcrumb trail uses this.currentBook + this.originCategory /
        // originDiscover / originAuthor (set above), none of which depend on
        // the async loads below.
        this.updateBreadcrumbs('book');

        // Load summaries, chapters, and related books
        await Promise.all([
            this.loadConciseSummary(),
            this.loadMediumSummary(),
            this.loadChapters(),
            this.loadRelatedBooks()
        ]);

        // Show resume reading button if user has progress
        await this.showResumeReadingButton();

        // Update URL
        this.updateURL(book);

        // Update page title
        this.updatePageTitle(`${book.title} by ${book.author} | Summra`);

        // Setup save for offline button (PWA-only feature)
        this.setupSaveOfflineButton();
    }

    showBookDetail(restoreScroll = false) {
        const pageKey = `book_${this.currentBook?.id || ''}`;
        this.setCurrentPage(pageKey);

        // Show only summary section
        this.showOnlySections('summary-section');

        // Hide admin edit button (only shown on chapter pages)
        const adminEditBtn = document.getElementById('admin-edit-chapter-btn');
        if (adminEditBtn) {
            adminEditBtn.classList.add('hidden');
        }

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }
    }

    updateAboutSection(book) {
        // Get section and elements
        const aboutSection = document.getElementById('about-section');
        const aboutText = document.getElementById('about-text');
        const relevanceText = document.getElementById('relevance-text');
        const authorBioText = document.getElementById('author-bio-text');
        const bookAuthor = document.getElementById('book-author');
        const authorLearnMoreBtn = document.getElementById('author-learn-more-btn');

        // Check if we have any data to display (backward compatibility)
        const hasAbout = book.about_text && book.about_text.trim();
        const hasCountry = book.author_country && book.author_country.trim();
        const hasBio = book.author_bio && book.author_bio.trim();
        const hasCharacterGuide = book.character_guide_url && book.character_guide_url.trim();
        const hasTimeline = book.timeline_url && book.timeline_url.trim();
        const hasThemes = book.themes_url && book.themes_url.trim();

        // Debug logging
        console.log('updateAboutSection called for:', book.title);
        console.log('Has metadata:', { hasAbout, hasCountry, hasBio, hasCharacterGuide, hasTimeline, hasThemes });

        // Update book author with country information
        const authorName = book.author || '';
        const authorSlug = this.slugify(authorName);

        if (bookAuthor) {
            const countryText = hasCountry ? ` (${book.author_country})` : '';
            bookAuthor.innerHTML = `by <a href="${withBasePath(`/authors/${authorSlug}`)}" class="author-link">${this.escapeHtml(authorName)}</a>${countryText}`;
        }

        // Update author "Learn more" button
        if (authorLearnMoreBtn && authorName) {
            authorLearnMoreBtn.href = `/authors/${authorSlug}`;
            authorLearnMoreBtn.classList.remove('hidden');
        }

        // Always call updateReadingGuide to remove loading spinners
        this.updateReadingGuide(book, hasCharacterGuide, hasTimeline, hasThemes);

        // Only show section if we have at least some data
        if (!hasAbout && !hasBio && !hasCharacterGuide && !hasTimeline && !hasThemes) {
            if (aboutSection) aboutSection.classList.add('hidden');
            return;
        }

        // Show section
        if (aboutSection) aboutSection.classList.remove('hidden');

        // Populate about text
        if (aboutText) {
            aboutText.innerHTML = hasAbout ? this.renderMarkdown(book.about_text) : '';
            aboutText.parentElement.style.display = hasAbout ? 'block' : 'none';
        }

        // Populate author bio
        if (authorBioText) {
            const hasBio = book.author_bio && book.author_bio.trim();
            if (hasBio) {
                authorBioText.innerHTML = this.renderMarkdown(book.author_bio);
                authorBioText.style.display = 'block';
                authorBioText.parentElement.style.display = 'block';
            } else {
                authorBioText.innerHTML = '';
                authorBioText.style.display = 'none';
                // Keep the parent visible if we have an author (for the "Learn more" button)
                if (authorName) {
                    authorBioText.parentElement.style.display = 'block';
                } else {
                    authorBioText.parentElement.style.display = 'none';
                }
            }
        }
    }

    updateReadingGuide(book, hasCharacterGuide, hasTimeline, hasThemes) {
        const readingGuideSection = document.getElementById('reading-guide-section');
        const characterGuideImage = document.getElementById('character-guide-image');
        const timelineGuideImage = document.getElementById('timeline-guide-image');
        const themesGuideImage = document.getElementById('themes-guide-image');

        // ALWAYS remove loading spinner and skeleton placeholders from all tab contents
        // (This needs to happen whether or not we have guide content)
        const themesContent = document.getElementById('reading-tab-themes');
        const charactersContent = document.getElementById('reading-tab-characters');
        const timelineContent = document.getElementById('reading-tab-timeline');

        [themesContent, charactersContent, timelineContent].forEach(content => {
            if (content) {
                const loadingContainer = content.querySelector('.loading-container');
                if (loadingContainer) loadingContainer.remove();
                const skeleton = content.querySelector('.skeleton');
                if (skeleton) skeleton.remove();
            }
        });

        // Show Reading Guide section if we have any guide content
        if (hasCharacterGuide || hasTimeline || hasThemes) {
            readingGuideSection.classList.remove('hidden');

            // Set up character guide image
            if (hasCharacterGuide && characterGuideImage) {
                characterGuideImage.src = book.character_guide_url;
                characterGuideImage.style.display = '';
                characterGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = book.character_guide_url.replace(/\.(png|jpg|jpeg|webp)$/i, '');
                        this.openLightbox(baseUrl, 'Character Guide');
                    }
                };
            }

            // Set up timeline image
            if (hasTimeline && timelineGuideImage) {
                timelineGuideImage.src = book.timeline_url;
                timelineGuideImage.style.display = '';
                timelineGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = book.timeline_url.replace(/\.(png|jpg|jpeg|webp)$/i, '');
                        this.openLightbox(baseUrl, 'Timeline');
                    }
                };
            }

            // Set up themes image
            if (hasThemes && themesGuideImage) {
                themesGuideImage.src = book.themes_url;
                themesGuideImage.style.display = '';
                themesGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = book.themes_url.replace(/\.(png|jpg|jpeg|webp)$/i, '');
                        this.openLightbox(baseUrl, 'Themes');
                    }
                };
            }

            // Show/hide tabs based on what's available
            const themesTab = document.querySelector('.reading-guide-tab[data-reading-tab="themes"]');
            const characterTab = document.querySelector('.reading-guide-tab[data-reading-tab="characters"]');
            const timelineTab = document.querySelector('.reading-guide-tab[data-reading-tab="timeline"]');

            const themesContent = document.getElementById('reading-tab-themes');
            const characterContent = document.getElementById('reading-tab-characters');
            const timelineContent = document.getElementById('reading-tab-timeline');

            // Reset all tabs first
            document.querySelectorAll('.reading-guide-tab').forEach(tab => {
                tab.classList.remove('active');
                tab.style.display = 'none';
            });
            document.querySelectorAll('.reading-guide-tab-content').forEach(content => {
                content.classList.remove('active');
            });

            // Determine which tab should be active first
            let firstActiveTab = null;
            let firstActiveContent = null;

            // Show Themes tab if available
            if (hasThemes && themesTab && themesContent) {
                themesTab.style.display = '';
                if (!firstActiveTab) {
                    firstActiveTab = themesTab;
                    firstActiveContent = themesContent;
                }
            }

            // Show Characters tab if available
            if (hasCharacterGuide && characterTab && characterContent) {
                characterTab.style.display = '';
                if (!firstActiveTab) {
                    firstActiveTab = characterTab;
                    firstActiveContent = characterContent;
                }
            }

            // Show Timeline tab if available
            if (hasTimeline && timelineTab && timelineContent) {
                timelineTab.style.display = '';
                if (!firstActiveTab) {
                    firstActiveTab = timelineTab;
                    firstActiveContent = timelineContent;
                }
            }

            // Activate the first available tab
            if (firstActiveTab && firstActiveContent) {
                firstActiveTab.classList.add('active');
                firstActiveContent.classList.add('active');
            }
        } else {
            readingGuideSection.classList.add('hidden');
        }
    }

    async loadBookMetadata(bookId) {
        // Get elements
        const aboutSection = document.getElementById('about-section');
        const aboutText = document.getElementById('about-text');
        const authorBioText = document.getElementById('author-bio-text');
        const readingGuideSection = document.getElementById('reading-guide-section');

        // Only show loading spinner if content is empty
        const shouldShowLoading = aboutText && !aboutText.textContent.trim();

        if (shouldShowLoading && aboutSection && aboutText && authorBioText) {
            aboutSection.classList.remove('hidden');
            aboutText.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading book information...</div>
                </div>
            `;
            aboutText.parentElement.style.display = 'block';
            authorBioText.innerHTML = '';
            authorBioText.parentElement.style.display = 'none';
        }

        // Show loading spinner in Reading Guide section only if empty
        if (shouldShowLoading && readingGuideSection) {
            readingGuideSection.classList.remove('hidden');
            const themesGuideImage = document.getElementById('themes-guide-image');
            const characterGuideImage = document.getElementById('character-guide-image');
            const timelineGuideImage = document.getElementById('timeline-guide-image');

            if (themesGuideImage) themesGuideImage.style.display = 'none';
            if (characterGuideImage) characterGuideImage.style.display = 'none';
            if (timelineGuideImage) timelineGuideImage.style.display = 'none';

            // Add loading spinner to the first tab content
            const themesContent = document.getElementById('reading-tab-themes');

            const loadingHtml = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading reading guide...</div>
                </div>
            `;
            if (themesContent && !themesContent.querySelector('.loading-container')) {
                themesContent.insertAdjacentHTML('afterbegin', loadingHtml);
            }
        }

        // Fetch full book data from API to get metadata fields
        try {
            const response = await fetch(`${this.apiBase}/books/${bookId}`);
            const data = await response.json();

            if (data.success && data.book) {
                // Update the about section with the full book data
                this.updateAboutSection(data.book);
            }
        } catch (error) {
            console.error('Error loading book metadata:', error);
            // Silently fail - section will remain hidden
            if (aboutSection) aboutSection.classList.add('hidden');
        }
    }

    collapseConciseSummary() {
        const previewContainer = document.getElementById('concise-preview-container');
        const expandButton = document.getElementById('concise-expand-button');
        const previewFade = document.getElementById('concise-preview-fade');

        if (!previewContainer || !expandButton || !previewFade) return;

        // Collapse the summary
        previewContainer.classList.remove('expanded');
        previewFade.classList.remove('hidden');
        expandButton.textContent = 'Read more';
        this.conciseSummaryExpanded = false;
    }

    async loadConciseSummary() {
        const conciseSummaryText = document.getElementById('concise-summary-text');

        // Only show loading spinner if the content is empty
        if (!conciseSummaryText.textContent.trim()) {
            conciseSummaryText.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading summary...</div>
                </div>
            `;
        }

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/concise`);
            const data = await response.json();

            if (data.success && data.summary) {
                conciseSummaryText.innerHTML = this.renderMarkdown(data.summary.content);

                // Store concise summary data for TTS
                this.conciseSummaryContent = data.summary.content;
                this.conciseSummaryHasAudio = data.has_audio || false;

                // Update the unified TTS button
                this.updateSummaryTTSButton();

                // Check if content height exceeds the preview container max-height
                const previewContainer = document.getElementById('concise-preview-container');
                const expandButton = document.getElementById('concise-expand-button');
                const previewFade = document.getElementById('concise-preview-fade');

                // Use setTimeout to ensure content is rendered and height is calculated
                setTimeout(() => {
                    const contentHeight = conciseSummaryText.scrollHeight;
                    const containerMaxHeight = 300; // Match CSS max-height

                    if (contentHeight > containerMaxHeight) {
                        // Show expand button if content is taller than container
                        expandButton.classList.remove('hidden');

                        // Setup expand/collapse toggle
                        expandButton.onclick = () => {
                            this.conciseSummaryExpanded = !this.conciseSummaryExpanded;

                            if (this.conciseSummaryExpanded) {
                                // Expand
                                previewContainer.classList.add('expanded');
                                previewFade.classList.add('hidden');
                                expandButton.textContent = 'Show Less ↑';
                            } else {
                                // Collapse
                                previewContainer.classList.remove('expanded');
                                previewFade.classList.remove('hidden');
                                expandButton.textContent = 'Read more';

                                // Scroll back to the top of the Quick Summary section
                                document.getElementById('concise-summary-section').scrollIntoView({
                                    behavior: 'smooth',
                                    block: 'start'
                                });
                            }
                        };
                    }
                }, 100);
            } else {
                conciseSummaryText.innerHTML = '<p class="error">Summary not available</p>';
            }
        } catch (error) {
            console.error('Error loading concise summary:', error);
            conciseSummaryText.innerHTML = '<p class="error">Error loading summary</p>';
        }
    }

    async loadMediumSummary() {
        const mediumPreviewText = document.getElementById('medium-preview-text');

        // Only show loading spinner if the content is empty
        if (!mediumPreviewText.textContent.trim()) {
            mediumPreviewText.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading full summary...</div>
                </div>
            `;
        }

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/medium`);
            const data = await response.json();

            if (data.success && data.summary) {
                this.mediumSummaryContent = data.summary.content;
                this.mediumSummaryHasAudio = data.has_audio || false; // Cache the audio flag
                // Show full content in preview (will be faded by CSS)
                mediumPreviewText.innerHTML = this.renderMarkdown(this.mediumSummaryContent);

                // Update the unified TTS button
                this.updateSummaryTTSButton();

                // Setup expand button to navigate to new page
                const expandBtn = document.getElementById('medium-expand-button');
                expandBtn.onclick = () => {
                    this.updateURL(this.currentBook, 'summary');
                    this.showMediumDetail(this.currentBook);
                };
            } else {
                mediumPreviewText.innerHTML = '<p class="error">Medium summary not available</p>';
            }
        } catch (error) {
            console.error('Error loading medium summary:', error);
            mediumPreviewText.innerHTML = '<p class="error">Error loading summary</p>';
        }
    }

    async loadChapters() {
        const chaptersList = document.getElementById('chapters-list');

        // Only show loading spinner if the content is empty
        if (!chaptersList.textContent.trim()) {
            chaptersList.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading chapters...</div>
                </div>
            `;
        }

        // Fetch completed chapters for styling
        let completedChapters = [];
        if (window.authModule && this.currentBook) {
            completedChapters = await window.authModule.getCompletedChaptersForBook(this.currentBook.id);
        }

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/chapters`);
            const data = await response.json();

            if (data.success && data.sections) {
                // Flatten chapters from all sections for compatibility
                this.chapters = [];
                data.sections.forEach(section => {
                    if (section.chapters) {
                        this.chapters.push(...section.chapters);
                    }
                });

                // Toggle "Chapters in Plain English" → "Chapters" + coming-soon
                // banner based on whether ANY chapter has a modern translation.
                // The chapters-list endpoint omits per-chapter modern text for
                // payload size, so trust the top-level has_modern_english flag.
                this.updatePlainEnglishUi(data.has_modern_english);

                chaptersList.innerHTML = '';

                // Check if book has two-level structure (multiple sections)
                if (data.has_sections && data.sections.length > 1) {
                    // Count sections with chapters
                    const totalSections = data.sections.length;
                    const sectionsWithChapters = data.sections.filter(s => s.chapters && s.chapters.length > 0).length;

                    // If no chapters at all yet, show section structure with processing message
                    if (this.chapters.length === 0) {
                        // Show section headers as placeholders
                        data.sections.forEach(section => {
                            const sectionHeader = document.createElement('div');
                            sectionHeader.className = 'section-header';
                            const sectionTitle = section.title ?
                                `${section.type} ${section.number}: ${section.title}` :
                                `${section.type} ${section.number}`;
                            sectionHeader.innerHTML = `<h4 style="opacity: 0.5;">${sectionTitle} <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-light);">(processing...)</span></h4>`;
                            chaptersList.appendChild(sectionHeader);
                        });

                        const note = document.createElement('p');
                        note.style.cssText = 'color: var(--text-light); font-size: 0.9rem; margin-top: 1rem; padding: 1rem; background: rgba(255, 255, 255, 0.05); border-radius: 8px;';
                        note.innerHTML = `<em>⏳ Processing in progress... 0/${totalSections} sections complete. Refresh to see newly added chapters.</em>`;
                        chaptersList.appendChild(note);
                        return;
                    }

                    // Render hierarchical structure (Book/Part/Act → Chapters)
                    data.sections.forEach(section => {
                        // Create section header (always show, even if no chapters yet)
                        const sectionHeader = document.createElement('div');
                        sectionHeader.className = 'section-header';
                        const sectionTitle = section.title ?
                            `${section.type} ${section.number}: ${section.title}` :
                            `${section.type} ${section.number}`;

                        // Dim the header if this section has no chapters yet
                        const hasChapters = section.chapters && section.chapters.length > 0;
                        const headerStyle = hasChapters ? '' : ' style="opacity: 0.5;"';
                        const processingLabel = hasChapters ? '' : ' <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-light);">(processing...)</span>';

                        sectionHeader.innerHTML = `<h4${headerStyle}>${sectionTitle}${processingLabel}</h4>`;
                        chaptersList.appendChild(sectionHeader);

                        // Render chapters in this section (if any)
                        if (hasChapters) {
                            section.chapters.forEach(chapter => {
                                const box = document.createElement('div');
                                const isCompleted = completedChapters.includes(chapter.chapter_number);
                                box.className = 'chapter-box indented' + (isCompleted ? ' completed' : '');

                                const title = chapter.chapter_title || `Chapter ${chapter.chapter_number}`;
                                const titleEl = document.createElement('h4');
                                titleEl.className = 'chapter-box-title';
                                titleEl.textContent = `${chapter.chapter_number}. ${title}`;

                                box.appendChild(titleEl);
                                box.addEventListener('click', () => {
                                    this.showChapterDetailPage(chapter.chapter_number);
                                });
                                chaptersList.appendChild(box);
                            });
                        }
                    });

                    // Add a note if the book is still being processed
                    if (sectionsWithChapters < totalSections) {
                        const note = document.createElement('p');
                        note.style.cssText = 'color: var(--text-light); font-size: 0.9rem; margin-top: 1rem; padding: 1rem; background: rgba(255, 255, 255, 0.05); border-radius: 8px;';
                        note.innerHTML = `<em>⏳ Processing in progress... ${sectionsWithChapters}/${totalSections} sections complete. Refresh to see newly added chapters.</em>`;
                        chaptersList.appendChild(note);
                    }
                } else {
                    // Render flat structure (traditional single-level chapters)
                    if (this.chapters.length === 0) {
                        chaptersList.innerHTML = '<p style="color: var(--text-light); font-size: 0.95rem;">Chapters are being generated. Check back soon.</p>';
                    } else {
                        this.chapters.forEach(chapter => {
                            const box = document.createElement('div');
                            const isCompleted = completedChapters.includes(chapter.chapter_number);
                            box.className = 'chapter-box' + (isCompleted ? ' completed' : '');

                            const title = chapter.chapter_title || `Chapter ${chapter.chapter_number}`;
                            const titleEl = document.createElement('h4');
                            titleEl.className = 'chapter-box-title';
                            titleEl.textContent = `${chapter.chapter_number}. ${title}`;

                            box.appendChild(titleEl);
                            box.addEventListener('click', () => {
                                this.showChapterDetailPage(chapter.chapter_number);
                            });
                            chaptersList.appendChild(box);
                        });
                    }
                }
            } else {
                chaptersList.innerHTML = '<p style="color: var(--text-light); font-size: 0.95rem;">Chapters are being generated. Check back soon.</p>';
                this.chapters = [];
            }
        } catch (error) {
            console.error('Error loading chapters:', error);
            chaptersList.innerHTML = '<p class="error">Error loading chapters</p>';
        }
    }

    // Adapts the chapters-section header and shows a "coming soon" banner
    // based on whether this book has any modern English chapter translation.
    // Books with at least one modern chapter keep the "Chapters in Plain English"
    // framing; books with none get a plain "Chapters" header plus a notice.
    updatePlainEnglishUi(hasModernEnglish) {
        const heading = document.getElementById('chapters-section-heading');
        const banner = document.getElementById('plain-english-coming-soon');
        const hasAnyModern = !!hasModernEnglish;
        if (heading) {
            heading.textContent = hasAnyModern ? 'Chapters in Plain English' : 'Chapters';
        }
        if (banner) {
            banner.classList.toggle('hidden', hasAnyModern);
        }
    }

    async loadRelatedBooks() {
        const relatedBooksSection = document.getElementById('related-books-section');
        const relatedBooksCarousel = document.getElementById('related-books-carousel');

        if (!relatedBooksSection || !relatedBooksCarousel) return;

        // Only show loading spinner if the content is empty
        if (!relatedBooksCarousel.textContent.trim()) {
            relatedBooksCarousel.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Loading related books...</div>
                </div>
            `;
        }

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/related`);
            const data = await response.json();

            if (data.success && data.related) {
                const allRelated = [
                    ...(data.related.by_author || []),
                    ...(data.related.by_category || []),
                    ...(data.related.by_country || [])
                ];

                // Remove duplicates (books may appear in multiple categories)
                const uniqueBooks = [];
                const seenIds = new Set();
                for (const book of allRelated) {
                    if (!seenIds.has(book.id)) {
                        seenIds.add(book.id);
                        uniqueBooks.push(book);
                    }
                }

                // Limit to 10 related books
                const relatedBooks = uniqueBooks.slice(0, 10);

                if (relatedBooks.length > 0) {
                    // Create carousel container
                    const carousel = document.createElement('div');
                    carousel.className = 'carousel-container';

                    // Add navigation buttons
                    const leftBtn = document.createElement('button');
                    leftBtn.className = 'carousel-nav-btn left';
                    leftBtn.innerHTML = '‹';
                    leftBtn.disabled = true;  // Start disabled (at beginning)

                    const rightBtn = document.createElement('button');
                    rightBtn.className = 'carousel-nav-btn right';
                    rightBtn.innerHTML = '›';
                    rightBtn.disabled = false;  // Start enabled (can scroll right)

                    // Create scroll container
                    const scrollContainer = document.createElement('div');
                    scrollContainer.className = 'related-books-scroll';

                    relatedBooks.forEach(book => {
                        const bookCard = document.createElement('div');
                        bookCard.className = 'related-book-card';

                        const coverImageHtml = book.cover_image_url
                            ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, 'related-book-cover')
                            : '';

                        bookCard.innerHTML = `
                            ${coverImageHtml}
                            <h4 class="related-book-title">${this.escapeHtml(book.title)}</h4>
                            <p class="related-book-author">${this.escapeHtml(book.author)}</p>
                        `;

                        bookCard.addEventListener('click', () => this.selectBook(book));
                        scrollContainer.appendChild(bookCard);
                    });

                    // Carousel navigation logic
                    const scrollAmount = 220; // Width of one card + gap

                    leftBtn.addEventListener('click', () => {
                        scrollContainer.scrollBy({ left: -scrollAmount * 3, behavior: 'smooth' });
                    });

                    rightBtn.addEventListener('click', () => {
                        scrollContainer.scrollBy({ left: scrollAmount * 3, behavior: 'smooth' });
                    });

                    // Update button states on scroll
                    const updateButtonStates = () => {
                        leftBtn.disabled = scrollContainer.scrollLeft <= 0;
                        rightBtn.disabled = scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 1;
                    };

                    scrollContainer.addEventListener('scroll', updateButtonStates);

                    // Wait for DOM to render before checking initial state
                    setTimeout(() => updateButtonStates(), 0);

                    carousel.appendChild(leftBtn);
                    carousel.appendChild(scrollContainer);
                    carousel.appendChild(rightBtn);
                    relatedBooksCarousel.innerHTML = '';
                    relatedBooksCarousel.appendChild(carousel);
                    relatedBooksSection.classList.remove('hidden');
                } else {
                    relatedBooksSection.classList.add('hidden');
                }
            } else {
                relatedBooksSection.classList.add('hidden');
            }
        } catch (error) {
            console.error('Error loading related books:', error);
            relatedBooksSection.classList.add('hidden');
        }
    }

    async showHomeSection() {
        this.saveScrollPosition();
        this.setCurrentPage('home');
        this.currentView = 'home';

        // #hero-section is always rendered by index.html (never swapped for an
        // empty placeholder — see its template comment), so navigating here
        // client-side from another page only needs to toggle visibility below;
        // the CTA listeners attached once at bootstrap (DOMContentLoaded) and
        // HeroSearch's own constructor both already found these elements on
        // first load and are still wired to them.

        // Show only hero section (uses centralized section management)
        this.showOnlySections('hero-section');

        // Load books only when needed for home page
        await this.ensureBooksLoaded();

        // Render top 10 carousel
        this.renderTop10Carousel();

        this.currentBook = null;
        this.currentCategory = null;
        this.currentSummaryType = null;
        this.currentChapter = null;
        this.mediumSummaryContent = null;
        this.originCategory = null;
        this.originDiscover = false;
        this.originAuthor = null;

        // Hide all breadcrumbs when on home page
        this.hideAllBreadcrumbs();

        this.restoreScrollPosition('home');

        // Update page title
        this.updatePageTitle('Free Classic Book Summaries, Chapter Summaries & Full Text | Summra');
    }

    // Keep backward compatibility
    showBooksSection() {
        this.showHomeSection();
    }

    async showCategoryDetail(categoryId, restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'category';
        const pageKey = `category_${categoryId}`;
        this.setCurrentPage(pageKey);

        // Show only category detail section
        this.showOnlySections('category-detail-section');

        // Check cache first
        let categoryData = this.categoryCache[categoryId];

        if (!categoryData) {
            // Try to build from already-loaded books (client-side filtering)
            // This avoids an API call in most cases
            const booksInCategory = this.allBooks.filter(book =>
                book.categories && book.categories.some(cat => cat.id === categoryId)
            );

            if (booksInCategory.length > 0) {
                // Find category info from the books' category data
                const categoryInfo = booksInCategory[0].categories.find(cat => cat.id === categoryId);

                categoryData = {
                    category: categoryInfo,
                    books: booksInCategory
                };

                // Cache for future use
                this.categoryCache[categoryId] = categoryData;
            } else {
                // Last resort: fetch from API
                try {
                    const response = await fetch(`${this.apiBase}/categories/${categoryId}/books`);
                    const data = await response.json();

                    if (data.success) {
                        categoryData = {
                            category: data.category,
                            books: data.books
                        };
                        this.categoryCache[categoryId] = categoryData;
                    }
                } catch (error) {
                    console.error('Error loading category:', error);
                }
            }
        }

        // Render cached or freshly fetched data
        if (categoryData) {
            // Store current category for breadcrumbs
            this.currentCategory = categoryData.category;

            // Show and set the title for category pages
            const titleElement = document.getElementById('category-detail-title');
            if (titleElement) {
                titleElement.style.display = '';
                titleElement.textContent = categoryData.category.name;
            }

            document.getElementById('category-detail-subtitle').textContent =
                `${categoryData.books.length} book${categoryData.books.length !== 1 ? 's' : ''}`;

            // Render books in grid
            const grid = document.getElementById('category-books-grid');
            grid.innerHTML = '';
            categoryData.books.forEach(book => {
                const bookCard = this.createBookCard(book);
                grid.appendChild(bookCard);
            });
        }

        this.finishPageTransition(
            'category',
            pageKey,
            restoreScroll,
            categoryData && categoryData.category
                ? `${categoryData.category.name} - Classic Books | Summra`
                : null
        );
    }

    async showAllCategories(restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'all-categories';
        this.setCurrentPage('all-categories');

        // Show only all categories section
        this.showOnlySections('all-categories-section');

        // Load books first (needed for filtering by category)
        await this.ensureBooksLoaded();

        // Load all categories with books
        try {
            const response = await fetch(`${this.apiBase}/categories`);
            const data = await response.json();

            if (data.success) {
                await this.displayAllCategories(data.categories);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }

        this.finishPageTransition(
            'all-categories',
            'all-categories',
            restoreScroll,
            'Browse Categories - Classic Book Summaries | Summra'
        );
    }

    async displayAllCategories(categories) {
        const container = document.getElementById('all-categories-container');
        container.innerHTML = '';

        // Use already-loaded books data to filter by category client-side
        // This avoids making API calls - we reuse the cache from displayCategories
        const categoriesWithBooks = categories.map(category => {
            // Check cache first (should be populated by displayCategories)
            if (this.categoryCache[category.id]) {
                return {
                    ...category,
                    bookCount: this.categoryCache[category.id].books.length,
                    books: this.categoryCache[category.id].books
                };
            }

            // If not cached, filter client-side from all books
            const booksInCategory = this.allBooks.filter(book =>
                book.categories && book.categories.some(cat => cat.id === category.id)
            );

            // Cache for future use
            if (booksInCategory.length > 0) {
                this.categoryCache[category.id] = {
                    category,
                    books: booksInCategory
                };
            }

            return {
                ...category,
                bookCount: booksInCategory.length,
                books: booksInCategory
            };
        });

        // Filter and sort
        const validCategories = categoriesWithBooks
            .filter(cat => cat.bookCount > 0)
            .sort((a, b) => b.bookCount - a.bookCount);

        // Render each category carousel
        validCategories.forEach(category => {
            this.renderCategoryCarousel(category, category.books, 'all-categories-container');
        });
    }

    async showAllBooksGrid(restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'all-books';
        this.setCurrentPage('all-books');

        // Clear category and discover state since we're not viewing those
        this.currentCategory = null;
        this.originDiscover = false;
        this.originAuthor = null;

        // Load books only when needed
        await this.ensureBooksLoaded();

        // Show only category detail section (reused for all books grid)
        this.showOnlySections('category-detail-section');

        // Hide the title for All Books page
        const titleElement = document.getElementById('category-detail-title');
        if (titleElement) titleElement.style.display = 'none';

        document.getElementById('category-detail-subtitle').textContent =
            `${this.allBooks.length} book${this.allBooks.length !== 1 ? 's' : ''}`;

        // Get list of offline-saved books to sort and mark them
        const offlineBooks = await this.getOfflineBooks();
        const offlineBookIdsSet = new Set(offlineBooks.bookIds || []);

        // Sort books: offline-saved books first, then alphabetically by title
        const sortedBooks = [...this.allBooks].sort((a, b) => {
            const aIsOffline = offlineBookIdsSet.has(a.id);
            const bIsOffline = offlineBookIdsSet.has(b.id);

            // Offline books come first
            if (aIsOffline && !bIsOffline) return -1;
            if (!aIsOffline && bIsOffline) return 1;

            // Within the same category (both offline or both online), sort alphabetically
            return a.title.localeCompare(b.title);
        });

        // Render sorted books in grid
        const grid = document.getElementById('category-books-grid');
        grid.innerHTML = '';
        sortedBooks.forEach(book => {
            const isOffline = offlineBookIdsSet.has(book.id);
            const bookCard = this.createBookCard(book, isOffline);
            grid.appendChild(bookCard);
        });

        this.finishPageTransition(
            'category',
            'all-books',
            restoreScroll,
            'Browse Classic Books - Free Summaries | Summra'
        );
    }

    async showAuthorDetail(authorName, restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'author';
        this.setCurrentPage(`author-${authorName}`);

        // Show only author detail section
        this.showOnlySections('author-detail-section');

        // Create author detail section if it doesn't exist
        let authorSection = document.getElementById('author-detail-section');
        if (!authorSection) {
            authorSection = this.createAuthorDetailSection();
            document.querySelector('.main-content').appendChild(authorSection);
        }

        // Fetch author data
        try {
            const authorSlug = this.slugify(authorName);
            const [authorResponse, booksResponse] = await Promise.all([
                fetch(withBasePath(`/api/authors/${authorSlug}`)),
                fetch(withBasePath(`/api/authors/${authorSlug}/books`))
            ]);

            if (!authorResponse.ok) {
                throw new Error('Author not found');
            }

            const authorData = await authorResponse.json();
            const booksData = await booksResponse.json();

            // Render author page
            this.renderAuthorPage(authorData.author, booksData.books || []);

            // Update breadcrumbs
            this.updateBreadcrumbs('author', authorData.author);

            // Update page title
            this.updatePageTitle(`${authorName} - Author | Summra`);

            if (restoreScroll) {
                this.restoreScrollPosition(`author-${authorName}`);
            } else {
                window.scrollTo(0, 0);
            }
        } catch (error) {
            console.error('Error loading author:', error);
            const container = document.getElementById('author-detail-container');
            container.innerHTML = `
                <div class="error-message">
                    <h2>Author not found</h2>
                    <p>The author "${this.escapeHtml(authorName)}" could not be found.</p>
                    <button onclick="window.history.back()">Go Back</button>
                </div>
            `;
        }
    }

    async showDiscoverPage(restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'discover';
        this.setCurrentPage('discover');

        // Show only discover section
        this.showOnlySections('discover-section');

        // Create discover section if it doesn't exist
        let discoverSection = document.getElementById('discover-section');
        if (!discoverSection) {
            discoverSection = this.createDiscoverSection();
            document.querySelector('.main-content').appendChild(discoverSection);
        }

        // Ensure books are loaded (needed for popular carousel)
        await this.ensureBooksLoaded();

        // Fetch carousel data
        try {
            const response = await fetch(withBasePath('/api/discover/carousels'));
            const data = await response.json();

            if (!data.success) {
                throw new Error('Failed to fetch discover carousels');
            }

            // Render discover page
            this.renderDiscoverPage(data);

            // Update breadcrumbs
            this.updateBreadcrumbs('discover');

            // Update page title
            this.updatePageTitle('Discover Classic Books | Summra');

            if (restoreScroll) {
                this.restoreScrollPosition('discover');
            } else {
                window.scrollTo(0, 0);
            }
        } catch (error) {
            console.error('Error loading discover page:', error);
            discoverSection.innerHTML = `
                <div class="error-message">
                    <h2>Error loading page</h2>
                    <p>Could not load the discover page. Please try again later.</p>
                    <button onclick="window.location.href='${summraBasePath()}/'">Go Home</button>
                </div>
            `;
        }
    }

    createDiscoverSection() {
        const section = document.createElement('div');
        section.id = 'discover-section';
        section.className = 'content-section';
        return section;
    }

    renderDiscoverPage(data) {
        const section = document.getElementById('discover-section');

        // Clear existing content
        section.innerHTML = `
            <nav class="breadcrumb-nav" id="breadcrumb-nav-discover" aria-label="Breadcrumb">
                <ol class="breadcrumb-list" id="breadcrumb-list-discover">
                    <!-- Breadcrumbs will be dynamically loaded here -->
                </ol>
            </nav>
            <div id="discover-popular-carousel-wrapper"></div>
            <div class="categories-container" id="discover-carousels-container"></div>
        `;

        // Render popular carousel at the top (same as home page top 10)
        this.renderTop10AsStandardCarousel('discover-popular-carousel-wrapper', 'Popular');

        // Render each carousel using the same method as categories page
        if (data.carousels && data.carousels.length > 0) {
            for (const carousel of data.carousels) {
                this.renderCategoryCarousel(
                    { id: carousel.id, name: carousel.title, description: carousel.description },
                    carousel.books,
                    'discover-carousels-container'
                );
            }
        } else {
            const container = document.getElementById('discover-carousels-container');
            container.innerHTML = '<p class="no-content">No collections available at this time.</p>';
        }
    }

    createAuthorDetailSection() {
        const section = document.createElement('div');
        section.id = 'author-detail-section';
        section.className = 'content-section';
        return section;
    }

    renderAuthorPage(author, books) {
        const container = document.getElementById('author-detail-container');

        // Store current author for breadcrumbs
        this.currentAuthor = author;

        // Filter out books that are already on Summra
        const allOtherBooks = author.other_books || [];
        const booksOnSummra = books.map(b => this.normalizeBookTitle(b.title));

        const otherBooks = allOtherBooks.filter(bookTitle => {
            const normalizedTitle = this.normalizeBookTitle(bookTitle);
            // Check if this book is already on Summra using fuzzy matching
            return !booksOnSummra.some(summraTitle =>
                this.fuzzyMatchTitles(normalizedTitle, summraTitle)
            );
        });

        // Split other_books into chunks of 2 for two-column layout
        const otherBooksColumns = [];
        for (let i = 0; i < otherBooks.length; i += Math.ceil(otherBooks.length / 2)) {
            otherBooksColumns.push(otherBooks.slice(i, i + Math.ceil(otherBooks.length / 2)));
        }

        container.innerHTML = `
            <div class="author-header">
                <h1>${this.escapeHtml(author.name)}</h1>
                ${author.country ? `<p class="author-country">${this.escapeHtml(author.country)}</p>` : ''}
            </div>

            ${author.long_bio ? `
                <div class="author-bio-section">
                    <h2>About the Author</h2>
                    <div class="author-long-bio">${this.renderMarkdown(author.long_bio)}</div>
                </div>
            ` : ''}

            ${books.length > 0 ? `
                <div class="author-books-section">
                    <h2>Books on Summra <span class="count">(${books.length})</span></h2>
                    <div id="author-books-carousel" class="books-carousel"></div>
                </div>
            ` : ''}

            ${otherBooks.length > 0 ? `
                <div class="author-other-books-section">
                    <h2>Other Notable Works</h2>
                    <div class="other-books-grid">
                        ${otherBooksColumns.map((column, idx) => `
                            <div class="other-books-column">
                                <ul>
                                    ${column.map(book => `<li>${this.escapeHtml(book)}</li>`).join('')}
                                </ul>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;

        // Render books carousel if we have books
        if (books.length > 0) {
            const carousel = container.querySelector('#author-books-carousel');
            books.forEach(book => {
                const bookCard = this.createBookCard(book);
                carousel.appendChild(bookCard);
            });
        }
    }

    createBookCard(book, isOffline = false) {
        const bookCard = document.createElement('div');
        bookCard.className = 'book-card';

        const coverImageHtml = book.cover_image_url
            ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, 'book-cover')
            : '';

        // Add offline badge if book is saved offline
        const offlineBadge = isOffline
            ? `<div class="offline-badge" title="Saved for offline reading">
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                       <polyline points="20 6 9 17 4 12"></polyline>
                   </svg>
               </div>`
            : '';

        bookCard.innerHTML = `
            ${coverImageHtml}
            ${offlineBadge}
            <h3>${this.escapeHtml(book.title)}</h3>
            <p class="author">by ${this.escapeHtml(book.author)}</p>
            <div class="meta">
                <p>${this.formatNumber(book.word_count)} words</p>
            </div>
        `;
        bookCard.addEventListener('click', () => this.selectBook(book));
        return bookCard;
    }

    async showBlogIndex(restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'blog';
        this.setCurrentPage('blog');

        // Show only blog index section
        this.showOnlySections('blog-index-section');

        // Initialize and render blog index component
        if (!this.blogIndex) {
            this.blogIndex = new BlogIndex(this);
        }
        await this.blogIndex.render();

        this.finishPageTransition(
            'blog',
            'blog',
            restoreScroll,
            'Blog - Classic Literature Guides | Summra'
        );
    }

    async showBlogPost(slug, restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'blog-post';
        this.setCurrentPage(`blog-post-${slug}`);

        // Show only blog post section
        this.showOnlySections('blog-post-section');

        // Initialize and render blog post component
        if (!this.blogPost) {
            this.blogPost = new BlogPost(this);
        }
        await this.blogPost.render(slug);

        // render() already calls updatePageTitle() with the real post title
        // when the post is found — only fall back to the generic placeholder
        // when it wasn't (render() leaves the title untouched in that case).
        this.finishPageTransition(
            'blog-post',
            `blog-post-${slug}`,
            restoreScroll,
            this.blogPost.post ? null : 'Blog Post | Summra'
        );
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatNumber(num) {
        return num.toLocaleString();
    }

    // ===== Skeleton Loading Helpers =====

    createImageWithSkeleton(src, alt, className) {
        // Create wrapper div
        const wrapper = document.createElement('div');
        wrapper.className = 'book-cover-wrapper';

        // Create skeleton placeholder
        const skeleton = document.createElement('div');
        skeleton.className = 'book-cover-skeleton';
        wrapper.appendChild(skeleton);

        // Create image
        const img = document.createElement('img');
        img.src = src;
        img.alt = alt;
        img.className = className;
        img.loading = 'lazy';

        // Handle image load
        img.addEventListener('load', () => {
            img.classList.add('loaded');
            // Remove skeleton after fade-in completes
            setTimeout(() => {
                if (skeleton.parentNode === wrapper) {
                    wrapper.removeChild(skeleton);
                }
            }, 300);
        });

        // Handle image error
        img.addEventListener('error', () => {
            // Remove skeleton on error too
            if (skeleton.parentNode === wrapper) {
                wrapper.removeChild(skeleton);
            }
        });

        wrapper.appendChild(img);
        return wrapper;
    }

    getImageHtml(imageUrl, alt, className) {
        if (!imageUrl) return '';

        // Escape attributes for safety
        const escapedAlt = this.escapeHtml(alt);

        // Prepend /static/ to the path if it starts with /covers/ or covers/ (for consistency with other pages)
        let fullImageUrl = imageUrl;
        if (imageUrl.startsWith('/covers/')) {
            fullImageUrl = '/static' + imageUrl;
        } else if (imageUrl.startsWith('covers/')) {
            fullImageUrl = '/static/' + imageUrl;
        }
        fullImageUrl = withBasePath(fullImageUrl);

        // Get base URL without extension
        const urlWithoutExt = fullImageUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');

        // Create picture element with WebP source and JPG fallback
        return `
            <div class="book-cover-wrapper">
                <div class="book-cover-skeleton"></div>
                <picture>
                    <source srcset="${this.escapeHtml(urlWithoutExt + '.webp')}" type="image/webp">
                    <img src="${this.escapeHtml(urlWithoutExt + '.jpg')}"
                         alt="${escapedAlt}"
                         class="${className}"
                         loading="lazy"
                         onload="this.classList.add('loaded'); setTimeout(() => { const skeleton = this.parentElement.previousElementSibling; if (skeleton && skeleton.classList.contains('book-cover-skeleton')) skeleton.remove(); }, 300);"
                         onerror="const skeleton = this.parentElement.previousElementSibling; if (skeleton && skeleton.classList.contains('book-cover-skeleton')) skeleton.remove();">
                </picture>
            </div>
        `;
    }



    setupLightbox() {
        /**
         * Setup image lightbox overlay for chapter illustrations.
         * When user clicks an illustration, it opens in a full-screen overlay.
         */
        const lightboxOverlay = document.getElementById('lightbox-overlay');
        const lightboxImage = document.getElementById('lightbox-image');
        const lightboxWebp = document.getElementById('lightbox-webp');
        const lightboxJpg = document.getElementById('lightbox-jpg');
        const lightboxClose = document.getElementById('lightbox-close');

        if (!lightboxOverlay || !lightboxImage || !lightboxClose) {
            return; // Lightbox elements not found
        }

        // Function to open lightbox
        const openLightbox = (imageSrc, imageAlt) => {
            // imageSrc is the base URL without extension
            const webpUrl = `${imageSrc}.webp`;
            const jpgUrl = `${imageSrc}.jpg`;

            // Set picture sources for WebP and JPG
            lightboxWebp.srcset = webpUrl;
            lightboxJpg.srcset = jpgUrl;
            lightboxImage.src = jpgUrl; // Fallback
            lightboxImage.alt = imageAlt || '';
            lightboxOverlay.classList.remove('hidden');
            // Prevent body scroll when lightbox is open
            document.body.style.overflow = 'hidden';
        };

        // Function to close lightbox
        const closeLightbox = () => {
            lightboxOverlay.classList.add('hidden');
            // Restore body scroll
            document.body.style.overflow = '';
        };

        // Close button click
        lightboxClose.addEventListener('click', (e) => {
            e.stopPropagation();
            closeLightbox();
        });

        // Click on overlay background (not the image)
        lightboxOverlay.addEventListener('click', (e) => {
            if (e.target === lightboxOverlay) {
                closeLightbox();
            }
        });

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !lightboxOverlay.classList.contains('hidden')) {
                closeLightbox();
            }
        });

        // Store reference to openLightbox function for use when loading chapters
        this.openLightbox = openLightbox;
    }


    setupAdminFeatures() {
        /**
         * Setup admin features for chapter editing (development only).
         * The edit button will show when viewing a chapter.
         */
        // Skip admin features in production mode
        if (!window.__IS_DEVELOPMENT__) {
            return;
        }

        const editBtn = document.getElementById('admin-edit-chapter-btn');
        const modal = document.getElementById('admin-edit-modal');
        const closeBtn = document.getElementById('admin-modal-close');
        const cancelBtn = document.getElementById('admin-cancel-btn');
        const saveBtn = document.getElementById('admin-save-btn');
        const chapterTextarea = document.getElementById('admin-chapter-text');
        const modernEnglishTextarea = document.getElementById('admin-modern-english');

        if (!editBtn || !modal) {
            return; // Admin features not available
        }

        // Show edit button only on chapter pages (will be toggled in showChapterDetail)
        // Open modal when edit button clicked
        editBtn.addEventListener('click', () => {
            // Populate modal with current chapter data
            if (this.currentChapter !== null && this.chapters.length > 0) {
                const chapter = this.chapters.find(c => c.chapter_number === this.currentChapter);
                if (chapter) {
                    chapterTextarea.value = chapter.chapter_text || '';
                    modernEnglishTextarea.value = chapter.modern_english_text || '';
                    modal.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';
                }
            }
        });

        // Close modal handlers
        const closeModal = () => {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        };

        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);

        // Click outside modal to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });

        // Save changes
        saveBtn.addEventListener('click', async () => {
            if (this.currentBook && this.currentChapter !== null) {
                const chapterText = chapterTextarea.value;
                const modernEnglish = modernEnglishTextarea.value;

                saveBtn.disabled = true;
                saveBtn.textContent = 'Saving...';

                try {
                    const response = await fetch(withBasePath(`/api/admin/chapters/${this.currentBook.id}/${this.currentChapter}`), {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            chapter_text: chapterText,
                            modern_english_text: modernEnglish
                        })
                    });

                    const data = await response.json();

                    if (data.success) {
                        // Update local chapter data
                        const chapterIndex = this.chapters.findIndex(c => c.chapter_number === this.currentChapter);
                        if (chapterIndex >= 0) {
                            this.chapters[chapterIndex].chapter_text = chapterText;
                            this.chapters[chapterIndex].modern_english_text = modernEnglish;
                        }

                        // Refresh the chapter display
                        await this.showChapterDetail(this.currentBook, this.currentChapter, false);

                        alert('Chapter updated successfully!');
                        closeModal();
                    } else {
                        alert(`Error: ${data.error}`);
                    }
                } catch (error) {
                    console.error('Error saving chapter:', error);
                    alert('Failed to save chapter. Please try again.');
                } finally {
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Save Changes';
                }
            }
        });
    }


    // Chapter dropdown removed - using simple summary button instead
}

Object.assign(SummraApp.prototype, paginationMixin);
Object.assign(SummraApp.prototype, settingsMixin);
Object.assign(SummraApp.prototype, breadcrumbsMixin);
Object.assign(SummraApp.prototype, offlineMixin);
Object.assign(SummraApp.prototype, audioMixin);
Object.assign(SummraApp.prototype, readerMixin);

// Hero Search Functionality
class HeroSearch {
    constructor() {
        this.searchInput = document.getElementById('hero-search-input');
        this.searchResults = document.getElementById('hero-search-results');
        this.debounceTimer = null;
        this.allBooks = [];

        if (this.searchInput && this.searchResults) {
            this.init();
        }
    }

    init() {
        // Fetch all books for search
        this.fetchBooks();

        // Add input event listener with debouncing
        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.debounceTimer);
            const query = e.target.value.trim();

            if (query.length === 0) {
                this.hideResults();
                return;
            }

            this.debounceTimer = setTimeout(() => {
                this.performSearch(query);
            }, 300);
        });

        // Hide results when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && !this.searchResults.contains(e.target)) {
                this.hideResults();
            }
        });

        // Handle Enter key to navigate to first result
        this.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const firstResult = this.searchResults.querySelector('.hero-search-result-item');
                if (firstResult) {
                    firstResult.click();
                }
            }
        });
    }

    async fetchBooks() {
        try {
            const response = await fetch(withBasePath('/api/books'));
            const data = await response.json();
            this.allBooks = data.books || [];
        } catch (error) {
            console.error('Error fetching books for search:', error);
        }
    }

    slugify(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/--+/g, '-')
            .trim();
    }

    performSearch(query) {
        const lowercaseQuery = query.toLowerCase();

        // Search in both title and author
        const results = this.allBooks.filter(book => {
            const titleMatch = book.title.toLowerCase().includes(lowercaseQuery);
            const authorMatch = book.author.toLowerCase().includes(lowercaseQuery);
            return titleMatch || authorMatch;
        });

        // Limit to top 8 results
        const limitedResults = results.slice(0, 8);

        this.displayResults(limitedResults, query);
    }

    displayResults(results, query) {
        if (results.length === 0) {
            this.searchResults.innerHTML = `
                <div class="hero-search-no-results">
                    No books found for "${query}"
                </div>
            `;
            this.showResults();
            return;
        }

        const resultsHtml = results.map(book => {
            const bookSlug = book.slug || this.slugify(book.title);
            return `
                <div class="hero-search-result-item" data-slug="${bookSlug}">
                    <img src="${summraBasePath()}/static/covers/${book.cover_image}"
                         alt="${book.title}"
                         class="hero-search-result-cover"
                         onerror="this.style.display='none'">
                    <div class="hero-search-result-info">
                        <h4 class="hero-search-result-title">${this.highlightMatch(book.title, query)}</h4>
                        <p class="hero-search-result-author">${this.highlightMatch(book.author, query)}</p>
                    </div>
                </div>
            `;
        }).join('');

        this.searchResults.innerHTML = resultsHtml;

        // Add click handlers to results (use pushState for client-side navigation to preserve audio)
        this.searchResults.querySelectorAll('.hero-search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const slug = item.dataset.slug;
                window.history.pushState(null, '', withBasePath(`/books/${slug}`));
                // Trigger the app's router to handle the new route
                if (window.summraApp) {
                    window.summraApp.handleRoute();
                }
            });
        });

        this.showResults();
    }

    highlightMatch(text, query) {
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<strong>$1</strong>');
    }

    showResults() {
        this.searchResults.classList.remove('hidden');
    }

    hideResults() {
        this.searchResults.classList.add('hidden');
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Store app instance globally for use by other components
    window.summraApp = new SummraApp();
    window.heroSearchInstance = new HeroSearch();

    // Handle hero banner CTAs with data-route attribute (use pushState to preserve audio)
    const heroCtas = document.querySelectorAll('[data-route]');
    heroCtas.forEach(cta => {
        cta.addEventListener('click', (e) => {
            e.preventDefault();
            const route = cta.dataset.route;

            // Special handling for "Read" CTA
            if (cta.id === 'hero-read-cta') {
                // Check screen width to determine which view mode to set
                const isMobile = window.innerWidth < 1024;
                const viewMode = isMobile ? 'modern' : 'side-by-side';

                // Set the view mode preference before navigation
                localStorage.setItem('reading_chapterViewMode', viewMode);
            }

            // Use pushState for client-side navigation (preserves audio)
            window.history.pushState(null, '', withBasePath(`/${route}`));
            window.summraApp.handleRoute();
        });
    });
});
