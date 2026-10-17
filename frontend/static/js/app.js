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
import { audioMixin } from './audio.js';
import { readerMixin } from './reader.js';

// Discover filters and their allowed values; same as DISCOVER_FILTERS in
// backend/routes/pages.py.
const DISCOVER_FILTERS = {
    grade: ['3-5', '6-8', '9-10', '11-12'],
    ages: ['lg', 'mg', 'mg-plus', 'ug'],
    school: ['yes'],
    plain: ['yes'],
    length: ['short', 'medium', 'long'],
};

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
        this.currentView = 'home'; // Track current view: 'home', 'book', 'category', 'all-categories', 'discover'
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
            currentViewMode: 'original' // Track current view mode for pagination
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
            'blog-post-section',
            'library-section',
            'continuous-reader-section'
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
        this.setupInstallPrompt();
        this.setupPagination();
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

        // In-page link to the Discover "How we grade books" panel.
        window.addEventListener('hashchange', () => this.revealHowWeGrade());

        // Intercept all link clicks for client-side routing
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href^="/"]');
            if (!link) return;

            // Leave new-tab clicks to the browser, and clicks another handler
            // already took (book cards, chapter rows) to that handler.
            if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;

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
            bookMatch, readerMatch, mediumMatch, chapterMatch, categoryMatch, categoriesMatch,
            allBooksMatch, discoverMatch, libraryMatch, authorMatch, blogMatch, blogPostMatch
        } = parseAppRoute(path);

        // Routes that don't need books data - proceed immediately
        if (libraryMatch) {
            await this.showLibrary();
        } else if (blogPostMatch) {
            const slug = blogPostMatch[1];
            await this.showBlogPost(slug, true);
        } else if (blogMatch) {
            await this.showBlogIndex(true);
        } else if (discoverMatch) {
            await this.showDiscoverPage(true);
        } else if (readerMatch) {
            const book = await this.resolveBookBySlug(readerMatch[1]);
            if (book) {
                const query = new URLSearchParams(window.location.search);
                await this.showContinuousReader(book, {
                    mode: query.get('mode'),
                    chapter: query.get('chapter'),
                });
            }
        } else if (chapterMatch) {
            const chapterNum = parseInt(chapterMatch[2]);
            const book = await this.resolveBookBySlug(chapterMatch[1]);
            if (book) {
                // Legacy chapter URLs open the same continuous reader at
                // the requested chapter, without a chapter destination.
                await this.showContinuousReader(book, { chapter: String(chapterNum), legacyChapterNumber: true });
            }
        } else if (mediumMatch) {
            const book = await this.resolveBookBySlug(mediumMatch[1]);
            if (book) {
                await this.showMediumDetail(book, true);
            }
        } else if (bookMatch) {
            const book = await this.resolveBookBySlug(bookMatch[1]);
            if (book) {
                await this.selectBook(book, true);
            }
        } else if (authorMatch) {
            // Author pages load from /api/authors/*, not the catalog.
            const authorName = decodeURIComponent(authorMatch[1]);
            await this.showAuthorDetail(authorName, true);
        } else if (categoryMatch) {
            // Filters the catalog if it's already loaded, otherwise uses
            // /api/categories/<id>/books — no need to wait for the catalog.
            const categoryId = parseInt(categoryMatch[1]);
            await this.showCategoryDetail(categoryId, true);
        } else if (categoriesMatch) {
            await this.showAllCategories(true);
        } else if (allBooksMatch) {
            // /books was folded into Discover (the server redirects too).
            window.history.replaceState({ type: 'discover' }, '', withBasePath('/discover'));
            await this.showDiscoverPage(true);
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
            const onChapter = showArray.includes('chapter-detail-section') ||
                showArray.includes('continuous-reader-section');
            footer.classList.toggle('hidden', onChapter);
        }

        // Toggle body class for chapter/medium reading pages. CSS uses this to
        // hide the site .header deterministically (replaces a body:has() rule
        // whose WebKit re-evaluation can lag a frame on iOS, leaking the site
        // nav over the chapter text after pushState navigation).
        const onReadingPage = showArray.includes('chapter-detail-section') ||
                              showArray.includes('medium-detail-section') ||
                              showArray.includes('continuous-reader-section');
        document.body.classList.toggle('on-chapter-page', onReadingPage);

        const onContinuousReader = showArray.includes('continuous-reader-section');
        // The reader's document must not scroll (CSS: body.on-reader-page).
        document.body.classList.toggle('on-reader-page', onContinuousReader);
        document.getElementById('reader-mode-settings')?.classList.toggle('hidden', !onContinuousReader);
        if (!onContinuousReader) {
            document.getElementById('reader-toc-panel')?.classList.add('hidden');
            document.getElementById('reading-settings-panel')?.classList.add('hidden');
        }

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
     * showAllCategories, showBlogIndex, showBlogPost):
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
                const targetTab = e.currentTarget.dataset.tab;

                // If switching to full summary and short summary is expanded, collapse it
                if (targetTab === '2000-word' && this.conciseSummaryExpanded) {
                    this.collapseConciseSummary();
                }

                // Remove active class from all tabs and contents
                document.querySelectorAll('.summary-tab').forEach(t => {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                document.querySelectorAll('.summary-tab-content').forEach(c => c.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                e.currentTarget.classList.add('active');
                e.currentTarget.setAttribute('aria-selected', 'true');
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

        // View All goes to the category page, or to Discover for the "All Books" shelf
        const viewAllHref = category.id === 'all' ? '/discover' : `/categories/${category.id}`;
        const viewAllLink = `<a href="${withBasePath(viewAllHref)}" class="view-all-link">View All →</a>`;

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
            scrollContainer.appendChild(this.createBookCard(book));
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
        const scrollContainer = document.getElementById('top-10-scroll');
        if (!scrollContainer) return;

        // On a full page load of / the cards are server-rendered (see
        // TOP_10_GUTENBERG_IDS in backend/routes/pages.py). Only build them
        // here when home was reached via SPA navigation from another route.
        if (!scrollContainer.querySelector('.top-10-book-card')) {
            // Top 10 most downloaded books from Project Gutenberg (by Gutenberg ID)
            const top10GutenbergIds = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345];

            const top10Books = [];
            top10GutenbergIds.forEach((gutenbergId) => {
                const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
                if (book) {
                    top10Books.push(book);
                }
            });
            if (top10Books.length === 0) return;

            // Clear skeleton loading cards
            scrollContainer.innerHTML = '';

            // Same card as the server-rendered shelf (book_card macro)
            top10Books.forEach((book) => {
                scrollContainer.appendChild(this.createBookCard(book, { className: 'top-10-book-card' }));
            });
        }

        // Listeners attach once; the container and buttons persist across
        // SPA navigations, so re-adding them would stack duplicate handlers.
        // Arrow state is recomputed each time home is shown: a scroll event
        // while the section was hidden (zero width) leaves them disabled.
        if (this.top10CarouselWired) {
            this.updateTop10Buttons();
            return;
        }
        this.top10CarouselWired = true;

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

        this.updateTop10Buttons = updateButtonStates;
        scrollContainer.addEventListener('scroll', updateButtonStates);
        setTimeout(() => updateButtonStates(), 100);
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

    loadBooks() {
        // One shared request: concurrent callers (router, HeroSearch) await the
        // same in-flight fetch instead of each downloading the catalog.
        this.booksPromise ||= this.fetchAllBooks();
        return this.booksPromise;
    }

    async fetchAllBooks() {
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

    // Resolve a /books/<slug>/... route's book. On a full page load the
    // server embedded it in __INITIAL_DATA__ (see _initial_book() in
    // backend/routes/pages.py), so there's no need to wait for the whole
    // /api/books catalog just to look up one slug.
    async resolveBookBySlug(slug) {
        // Route params come from location.pathname, which percent-encodes
        // non-ASCII slugs (louise-de-la-valli%C3%A8re); slugs are stored decoded.
        try { slug = decodeURIComponent(slug); } catch (_) { /* malformed: match as-is */ }
        if (!this.booksLoaded) {
            const initial = window.__INITIAL_DATA__?.book;
            if (initial?.slug === slug) return initial;
            await this.ensureBooksLoaded();
        }
        return this.allBooks.find(b => (b.slug || this.slugify(b.title)) === slug) || null;
    }

    async ensureBooksLoaded() {
        if (!this.booksLoaded) {
            await this.loadBooks();
        }
    }

    async selectBook(book, restoreScroll = false) {
        // Book cards open the editorial book page. Reading is an explicit
        // choice from its Read book control, which owns the /read route.
        if (this.continuousReader?.active) {
            await this.saveContinuousReader('navigation');
            this.continuousReader.active = false;
        }

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
        // If navigating from home, clear origin
        else if (this.currentView === 'home') {
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

        const slug = book.slug || this.slugify(book.title);
        const readLabel = document.getElementById('book-read-label');
        if (readLabel) readLabel.textContent = 'Start reading';
        document.getElementById('book-progress')?.classList.add('hidden');
        const sxsLink = document.getElementById('book-sxs-link');
        if (sxsLink) sxsLink.href = withBasePath(`/books/${slug}/read?mode=side_by_side`);

        const readButton = document.getElementById('book-read-btn');
        if (readButton) {
            readButton.onclick = async () => {
                const readerPath = withBasePath(`/books/${book.slug || this.slugify(book.title)}/read`);
                if (window.location.pathname !== readerPath) {
                    window.history.pushState({ type: 'reader', bookId: book.id }, '', readerPath);
                }
                await this.showContinuousReader(book);
            };
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

        // Signed-in readers: "Continue · <chapter>" and read checkmarks
        await this.applyBookProgress(book);

        // Update URL
        this.updateURL(book);

        // Update page title
        this.updatePageTitle(`${book.title} by ${book.author} | Summra`);
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
        const authorBioText = document.getElementById('author-bio-text');
        const bookAuthor = document.getElementById('book-author');
        const authorLearnMoreBtn = document.getElementById('author-learn-more-btn');

        // Check if we have any data to display (backward compatibility)
        const hasCountry = book.author_country && book.author_country.trim();
        const hasBio = book.author_bio && book.author_bio.trim();
        const hasCharacterGuide = book.character_guide_url && book.character_guide_url.trim();
        const hasTimeline = book.timeline_url && book.timeline_url.trim();
        const hasThemes = book.themes_url && book.themes_url.trim();

        // Debug logging
        console.log('updateAboutSection called for:', book.title);
        console.log('Has metadata:', { hasCountry, hasBio, hasCharacterGuide, hasTimeline, hasThemes });

        // Update book author with country information
        const authorName = book.author || '';
        const authorSlug = this.slugify(authorName);

        if (bookAuthor) {
            const countryText = hasCountry ? ` (${book.author_country})` : '';
            bookAuthor.innerHTML = `by <a href="${withBasePath(`/authors/${authorSlug}`)}" class="author-link">${this.escapeHtml(authorName)}</a>${countryText}`;
        }

        // Update author "Learn more" button
        if (authorLearnMoreBtn && authorName) {
            authorLearnMoreBtn.href = withBasePath(`/authors/${authorSlug}`);
            authorLearnMoreBtn.classList.remove('hidden');
        }

        // Always call updateReadingGuide to remove loading spinners
        this.updateReadingGuide(book, hasCharacterGuide, hasTimeline, hasThemes);

        // "About the author" sits after the chapters and only appears with a
        // bio. There's no "About this book": the summary already covers it.
        const authorSection = document.getElementById('about-author-section');
        if (authorSection) authorSection.classList.toggle('hidden', !hasBio);
        if (authorBioText) authorBioText.innerHTML = hasBio ? this.renderMarkdown(book.author_bio) : '';
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

            // Guide URLs are stored as /static/...; prefix them for /summrabook deployments.
            // Set up character guide image
            if (hasCharacterGuide && characterGuideImage) {
                const guideUrl = withBasePath(book.character_guide_url);
                characterGuideImage.src = guideUrl;
                characterGuideImage.style.display = '';
                characterGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = guideUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');
                        this.openLightbox(baseUrl, 'Character Guide');
                    }
                };
            }

            // Set up timeline image
            if (hasTimeline && timelineGuideImage) {
                const guideUrl = withBasePath(book.timeline_url);
                timelineGuideImage.src = guideUrl;
                timelineGuideImage.style.display = '';
                timelineGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = guideUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');
                        this.openLightbox(baseUrl, 'Timeline');
                    }
                };
            }

            // Set up themes image
            if (hasThemes && themesGuideImage) {
                const guideUrl = withBasePath(book.themes_url);
                themesGuideImage.src = guideUrl;
                themesGuideImage.style.display = '';
                themesGuideImage.onclick = () => {
                    if (this.openLightbox) {
                        // Remove extension from URL for lightbox
                        const baseUrl = guideUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');
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
        const authorBioText = document.getElementById('author-bio-text');
        const readingGuideSection = document.getElementById('reading-guide-section');

        // Only show loading state if this book's metadata isn't on the page yet
        const shouldShowLoading = this.loadedMetadataBookId !== bookId;

        if (shouldShowLoading && authorBioText) {
            authorBioText.innerHTML = '';
            document.getElementById('about-author-section')?.classList.add('hidden');
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
                // Update the author section with the full book data
                this.updateAboutSection(data.book);
                this.loadedMetadataBookId = bookId;
            }
        } catch (error) {
            // Silently fail - the author section stays hidden
            console.error('Error loading book metadata:', error);
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
        this.setSummaryMoreLabel(expandButton, false);
        this.conciseSummaryExpanded = false;
    }

    // "Read more ⌄" / "Show less ⌃" on the short summary.
    setSummaryMoreLabel(button, expanded) {
        const chevron = expanded ? 'M6 15l6-6 6 6' : 'M6 9l6 6 6-6';
        button.innerHTML = `${expanded ? 'Show less' : 'Read more'}<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="${chevron}"></path></svg>`;
        button.setAttribute('aria-expanded', String(expanded));
    }

    // " · 3 min" next to Short / Full in the summary switch.
    setSummaryReadingTime(elementId, markdown) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const words = (markdown || '').split(/\s+/).filter(Boolean).length;
        el.textContent = words ? ` · ${Math.max(1, Math.ceil(words / 230))} min` : '';
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
                this.setSummaryReadingTime('concise-summary-time', data.summary.content);

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
                                this.setSummaryMoreLabel(expandButton, true);
                            } else {
                                // Collapse
                                previewContainer.classList.remove('expanded');
                                previewFade.classList.remove('hidden');
                                this.setSummaryMoreLabel(expandButton, false);

                                // Scroll back to the top of the summary
                                document.getElementById('summary-tabs-section')?.scrollIntoView({
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
                this.setSummaryReadingTime('medium-summary-time', this.mediumSummaryContent);

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
                this.renderBookMeta(data.book, this.chapters.length, data.has_modern_english);

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
                                chaptersList.appendChild(this.createChapterRow(chapter, true));
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
                            chaptersList.appendChild(this.createChapterRow(chapter));
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

    // One row of the book page's table of contents: a link to the chapter
    // URL, which the router opens in the continuous reader at that chapter
    // (same as a direct load).
    createChapterRow(chapter, indented = false) {
        const row = document.createElement('a');
        row.className = 'chapter-box' + (indented ? ' indented' : '');
        row.dataset.chapterId = chapter.id;
        row.href = withBasePath(`/books/${this.currentBook.slug || this.slugify(this.currentBook.title)}/chapters/${chapter.chapter_number}`);
        const title = chapter.chapter_title || `Chapter ${chapter.chapter_number}`;
        row.innerHTML = `
            <span class="chapter-box-num">${chapter.chapter_number > 0 ? chapter.chapter_number : ''}</span>
            <h4 class="chapter-box-title">${this.escapeHtml(title)}</h4>
            ${chapter.reading_time ? `<span class="chapter-box-time">${this.escapeHtml(chapter.reading_time)}</span>` : ''}
            <span class="chapter-box-check" aria-label="Read">✓</span>
        `;
        return row;
    }

    // Meta row under the book title; same markup the server renders on
    // /books/<slug> (index.html, book_meta).
    renderBookMeta(book, chapterCount, hasPlainEnglish) {
        const meta = document.getElementById('book-meta');
        if (meta) {
            meta.innerHTML = [
                this.difficultyTagHtml(book),
                book?.ages_label ? `<span class="book-meta-item">${this.escapeHtml(book.ages_label)}</span>` : '',
                `<span class="book-meta-item">${chapterCount} chapter${chapterCount === 1 ? '' : 's'}</span>`,
                book?.reading_time ? `<span class="book-meta-item">${this.escapeHtml(book.reading_time)}</span>` : '',
                hasPlainEnglish ? '<span class="plain-english-badge">Plain English · grade 8</span>' : '<span class="original-only-tag">Original only</span>',
                ...(book?.school_lists || []).map(entry =>
                    `<a class="school-list-badge" href="${this.escapeHtml(entry.source)}" target="_blank" rel="noopener">Common Core · grades ${this.escapeHtml(entry.grade_band)}</a>`),
            ].join('');
        }
        document.getElementById('book-sxs-link')?.classList.toggle('hidden', !hasPlainEnglish);
    }

    // Reading state comes from the continuous reader's v2 projection: the
    // current place in the last-used mode drives the button and the progress
    // line under it, and chapters before the furthest place are checked (all
    // of them once finished).
    async applyBookProgress(book) {
        await window.authModule?.initAuth?.();
        const state = await window.authModule?.getReaderState?.(book.id);
        if (!state?.book || this.currentBook?.id !== book.id) return;
        const rows = [...document.querySelectorAll('#chapters-list .chapter-box')];
        const total = this.chapters.length;
        const finished = state.book.status === 'finished';
        const modeState = state.modes?.find(item => item.mode === state.book.last_mode);
        const index = id => this.chapters.findIndex(chapter => chapter.id === Number(id));
        const read = finished ? total : Math.max(0, index(modeState?.furthest_marker?.chapter_id));
        rows.forEach((row, i) => row.classList.toggle('completed', i < read));

        const currentIndex = index(modeState?.current_marker?.chapter_id);
        const current = this.chapters[currentIndex];
        const label = document.getElementById('book-read-label');
        const progress = document.getElementById('book-progress');
        if (!finished && !current) return;
        if (label) label.textContent = finished ? 'Read again' : 'Continue reading';
        if (!progress || !total) return;
        // Bar: how far through the book the current place is.
        const percent = finished ? 100 : Math.round(currentIndex * 100 / total);
        document.getElementById('book-progress-fill').style.width = `${percent}%`;
        document.getElementById('book-progress-text').innerHTML = finished
            ? 'Finished'
            : `Chapter ${currentIndex + 1} of ${total} · <span class="book-progress-where">${this.escapeHtml(current.chapter_title || `Chapter ${current.chapter_number}`)}</span>`;
        progress.classList.remove('hidden');
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
                        scrollContainer.appendChild(this.createBookCard(book));
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

        // Books are only needed to build the top-10 carousel client-side;
        // a full page load of / already has it server-rendered.
        if (!document.querySelector('#top-10-scroll .top-10-book-card')) {
            await this.ensureBooksLoaded();
        }

        // Render top 10 carousel
        this.renderTop10Carousel();
        this.wireHeroExamples();
        this.renderHomeContinue();

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

    // "Another example" steps through the hero's sentence pairs.
    wireHeroExamples() {
        const next = document.getElementById('hero-sentence-next');
        if (!next || this.heroExamplesWired) return;
        this.heroExamplesWired = true;
        next.addEventListener('click', () => {
            const pairs = [...document.querySelectorAll('#hero-examples .hero-sentence')];
            const current = pairs.findIndex(pair => !pair.hidden);
            pairs.forEach((pair, i) => {
                pair.hidden = i !== (current + 1) % pairs.length;
                pair.classList.toggle('is-new', !pair.hidden);
            });
        });
    }

    // Signed-in readers with a book in progress get it at the top of home.
    async renderHomeContinue() {
        const section = document.getElementById('home-continue');
        const container = document.getElementById('home-continue-cards');
        if (!section || !container) return;
        await window.authModule?.initAuth?.();
        if (!window.authModule?.currentUser?.()) {
            section.classList.add('hidden');
            return;
        }
        const library = await window.authModule.getLibrary();
        const books = (library?.continue_reading || []).slice(0, 3);
        if (this.currentView !== 'home') return;
        this.renderLibraryCards(container, books, 'Continue');
        section.classList.toggle('hidden', books.length === 0);
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

        // Load the catalog (needed for filtering by category) and the
        // category list in parallel
        try {
            const [response] = await Promise.all([
                fetch(`${this.apiBase}/categories`),
                this.ensureBooksLoaded(),
            ]);
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

            this.finishPageTransition(
                'author',
                `author-${authorName}`,
                restoreScroll,
                `${authorName} - Author | Summra`
            );
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
        this.showOnlySections('discover-section');

        // /discover is server-rendered with every card; reached in-app from
        // another page, the grid is empty and is filled from the catalog.
        const grid = document.getElementById('discover-grid');
        if (!grid.querySelector('.book-card')) {
            await this.ensureBooksLoaded();
        }
        // Re-check after the await: a second navigation may have filled it.
        if (!grid.querySelector('.book-card')) {
            this.allBooks
                .filter(book => book.slug)
                .forEach(book => grid.appendChild(this.createBookCard(book)));
        }
        this.wireDiscoverControls();

        const query = new URLSearchParams(window.location.search);
        this.setDiscoverFilters(Object.fromEntries(
            [...Object.keys(DISCOVER_FILTERS), 'sort'].map(name => [name, query.get(name)])
        ), false);

        this.finishPageTransition('discover', 'discover', restoreScroll, 'Discover Classic Books | Summra');
        this.revealHowWeGrade();
    }

    // /discover#how-we-grade (linked from the home page and the Discover
    // intro) opens the "How we grade books" panel and scrolls to it.
    revealHowWeGrade() {
        const panel = document.getElementById('how-we-grade');
        if (window.location.hash !== '#how-we-grade' || !panel) return;
        panel.open = true;
        panel.scrollIntoView({ block: 'start' });
    }

    // Controls persist across SPA navigations, so wire them once.
    wireDiscoverControls() {
        if (this.discoverWired) return;
        this.discoverWired = true;
        const section = document.getElementById('discover-section');
        section.querySelectorAll('.filter-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const { filter, value } = chip.dataset;
                // A toggle chip (Common Core texts) switches its filter off again.
                const next = chip.classList.contains('filter-chip--toggle') && this.discoverState[filter] === value ? 'all' : value;
                this.setDiscoverFilters({ ...this.discoverState, [filter]: next });
            });
        });
        document.getElementById('discover-sort').addEventListener('change', (e) => {
            this.setDiscoverFilters({ ...this.discoverState, sort: e.target.value });
        });
        section.querySelector('.discover-empty button').addEventListener('click', () => {
            this.setDiscoverFilters({ sort: this.discoverState.sort });
        });
    }

    // Filtering is CSS: the grid's data-filter-<name> attributes hide cards
    // whose data-<name> differs (same mechanism the server-rendered page uses).
    setDiscoverFilters(values, updateUrl = true) {
        const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);
        const state = Object.fromEntries(Object.entries(DISCOVER_FILTERS).map(([name, allowed]) => [name, pick(values[name], allowed, 'all')]));
        state.sort = pick(values.sort, ['title', 'shortest', 'easiest'], 'title');
        this.discoverState = state;

        const section = document.getElementById('discover-section');
        const grid = document.getElementById('discover-grid');
        Object.keys(DISCOVER_FILTERS).forEach(name => { grid.dataset[`filter${name[0].toUpperCase()}${name.slice(1)}`] = state[name]; });
        section.querySelectorAll('.filter-chip').forEach(chip => {
            chip.setAttribute('aria-pressed', String(chip.dataset.value === state[chip.dataset.filter]));
        });
        document.getElementById('discover-sort').value = state.sort;
        this.applySortToDiscoverGrid(grid, state.sort);

        const count = [...grid.children].filter(card =>
            Object.keys(DISCOVER_FILTERS).every(name => state[name] === 'all' || card.dataset[name] === state[name])
        ).length;
        document.getElementById('discover-count').textContent = `${count} book${count === 1 ? '' : 's'}`;
        section.querySelector('.discover-empty').classList.toggle('hidden', count > 0);

        if (updateUrl) {
            const params = new URLSearchParams();
            Object.keys(DISCOVER_FILTERS).forEach(name => { if (state[name] !== 'all') params.set(name, state[name]); });
            if (state.sort !== 'title') params.set('sort', state.sort);
            const qs = params.toString();
            window.history.replaceState(window.history.state, '', withBasePath(`/discover${qs ? `?${qs}` : ''}`));
        }
    }

    // Same ordering as DISCOVER_SORTS in backend/routes/pages.py.
    applySortToDiscoverGrid(grid, sort) {
        const title = card => card.querySelector('.book-card-title').textContent.toLowerCase();
        const byTitle = (a, b) => (title(a) < title(b) ? -1 : title(a) > title(b) ? 1 : 0);
        const minutes = card => (card.dataset.minutes ? Number(card.dataset.minutes) : Infinity);
        const grade = card => (card.dataset.gradeValue ? Number(card.dataset.gradeValue) : Infinity);
        const compare = {
            title: byTitle,
            shortest: (a, b) => minutes(a) - minutes(b) || byTitle(a, b),
            easiest: (a, b) => grade(a) - grade(b) || byTitle(a, b),
        }[sort];
        [...grid.children].sort(compare).forEach(card => grid.appendChild(card));
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

    // The one book card used by every listing (Books, Categories, Discover,
    // Author, "You may also like", home "Start here"). A real link: the
    // delegated handler in setupRouting() opens it in-app, and modified
    // clicks open a new tab.
    createBookCard(book, { className = 'book-card' } = {}) {
        const bookCard = document.createElement('a');
        bookCard.className = className;
        bookCard.href = withBasePath(`/books/${book.slug || this.slugify(book.title)}`);
        // Read by Discover's CSS filters and sort (same attributes as the
        // server-rendered card in _book_card.html).
        bookCard.dataset.grade = book.grade_band || 'none';
        bookCard.dataset.ages = book.ages || 'none';
        bookCard.dataset.school = book.on_school_list ? 'yes' : 'no';
        bookCard.dataset.plain = book.has_plain_english ? 'yes' : 'no';
        bookCard.dataset.length = (book.length || 'none').toLowerCase();
        bookCard.dataset.minutes = book.reading_minutes || '';
        bookCard.dataset.gradeValue = book.grade ?? '';

        const levelHtml = this.difficultyTagHtml(book);
        const timeHtml = book.reading_time
            ? `<span class="book-card-time">${this.escapeHtml(book.reading_time)}</span>`
            : '';

        const originalOnlyHtml = book.has_plain_english ? '' : '<span class="original-only-tag">Original only</span>';

        bookCard.innerHTML = `
            ${this.bookCoverHtml(book)}
            <h3 class="book-card-title">${this.escapeHtml(book.title)}</h3>
            <p class="book-card-author">${this.escapeHtml(book.author)}</p>
            <p class="book-card-meta">${levelHtml}${timeHtml}${originalOnlyHtml}</p>
        `;
        return bookCard;
    }

    // The original's level: "Original: Grade 7" (published ATOS level), or
    // nothing — the CEFR levels are estimates, not published. Plain English
    // has its own target (grade 8). Same as the difficulty_tag macro in
    // _book_card.html.
    difficultyTagHtml(book) {
        return book?.grade_label
            ? `<span class="grade-tag grade-tag--${this.escapeHtml(book.grade_band)}">Original: ${this.escapeHtml(book.grade_label)}</span>`
            : '';
    }

    // 2:3 cover box. The title is set in serif underneath the image, so a
    // slow or missing cover reads as a deliberate plain cover rather than a
    // grey blob, and every card keeps the same shape while loading.
    bookCoverHtml(book) {
        const sources = book.cover_image_url ? this.coverSources(book.cover_image_url) : null;
        const picture = sources ? `
                <picture>
                    <source srcset="${this.escapeHtml(sources.webp)}" type="image/webp">
                    <img src="${this.escapeHtml(sources.jpg)}" alt="${this.escapeHtml(`${book.title} cover`)}"
                         loading="lazy" onload="this.classList.add('loaded')" onerror="this.remove()">
                </picture>` : '';
        return `
            <div class="book-card-cover">
                <span class="book-card-cover-title" aria-hidden="true">${this.escapeHtml(book.title)}</span>${picture}
            </div>
        `;
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

    // WebP + JPG URLs for a stored cover path.
    coverSources(imageUrl) {
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
        return { webp: urlWithoutExt + '.webp', jpg: urlWithoutExt + '.jpg' };
    }

    getImageHtml(imageUrl, alt, className) {
        if (!imageUrl) return '';

        // Escape attributes for safety
        const escapedAlt = this.escapeHtml(alt);
        const sources = this.coverSources(imageUrl);

        // Create picture element with WebP source and JPG fallback
        return `
            <div class="book-cover-wrapper">
                <div class="book-cover-skeleton"></div>
                <picture>
                    <source srcset="${this.escapeHtml(sources.webp)}" type="image/webp">
                    <img src="${this.escapeHtml(sources.jpg)}"
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
Object.assign(SummraApp.prototype, audioMixin);
Object.assign(SummraApp.prototype, readerMixin);

// Hero Search Functionality
// Typeahead book search. One instance drives the home hero's box, another
// the header's (see DOMContentLoaded below).
class HeroSearch {
    constructor(inputId = 'hero-search-input', resultsId = 'hero-search-results') {
        this.searchInput = document.getElementById(inputId);
        this.searchResults = document.getElementById(resultsId);
        this.debounceTimer = null;
        this.allBooks = [];

        if (this.searchInput && this.searchResults) {
            this.init();
        }
    }

    init() {
        // The catalog is only needed once the reader searches; most pages
        // render without it, so don't download it on every page load.
        this.searchInput.addEventListener('focus', () => this.fetchBooks(), { once: true });

        // Add input event listener with debouncing
        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.debounceTimer);
            const query = e.target.value.trim();

            if (query.length === 0) {
                this.hideResults();
                return;
            }

            this.debounceTimer = setTimeout(async () => {
                await this.fetchBooks();
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
        await window.summraApp.ensureBooksLoaded();
        this.allBooks = window.summraApp.allBooks;
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
                    No books found for "${window.summraApp.escapeHtml(query)}"
                </div>
            `;
            this.showResults();
            return;
        }

        const resultsHtml = results.map(book => {
            const bookSlug = book.slug || this.slugify(book.title);
            const cover = book.cover_image_url ? window.summraApp.coverSources(book.cover_image_url).jpg : '';
            return `
                <div class="hero-search-result-item" data-slug="${window.summraApp.escapeHtml(bookSlug)}">
                    ${cover ? `<img src="${window.summraApp.escapeHtml(cover)}"
                         alt=""
                         class="hero-search-result-cover"
                         onerror="this.style.display='none'">` : ''}
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

    // Escapes both the text and the query, so neither can inject markup.
    highlightMatch(text, query) {
        const escape = window.summraApp.escapeHtml.bind(window.summraApp);
        const pattern = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return text.split(new RegExp(`(${pattern})`, 'gi'))
            .map((part, i) => (i % 2 ? `<strong>${escape(part)}</strong>` : escape(part)))
            .join('');
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
    window.headerSearchInstance = new HeroSearch('header-search-input', 'header-search-results');

    // Header search: the magnifier opens a search box available on every page.
    const headerSearch = document.getElementById('header-search');
    const headerToggle = document.getElementById('header-search-toggle');
    headerToggle?.addEventListener('click', () => {
        const open = headerSearch.classList.toggle('open');
        headerToggle.setAttribute('aria-expanded', String(open));
        if (open) document.getElementById('header-search-input').focus();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && headerSearch?.classList.contains('open')) {
            headerSearch.classList.remove('open');
            headerToggle.setAttribute('aria-expanded', 'false');
        }
    });
});
