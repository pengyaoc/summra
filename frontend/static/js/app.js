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

class SummraApp {
    constructor() {
        this.apiBase = '/api';
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
    }

    registerServiceWorker() {
        // Register service worker for PWA functionality
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/service-worker.js')
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
                    })
                    .catch((error) => {
                        console.log('❌ Service Worker registration failed:', error);
                    });
            });
        } else {
            console.log('⚠️  Service Workers not supported in this browser');
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
            if (href.startsWith('/') && !href.startsWith('/api/') && !href.startsWith('/static/')) {
                e.preventDefault();
                window.history.pushState(null, '', href);
                this.handleRoute();
            }
        });

        // Handle the initial route immediately
        this.handleRoute();
    }

    async handleRoute() {
        // Use pathname for routing (clean URLs)
        const path = window.location.pathname;

        // Home page
        if (!path || path === '/') {
            this.showHomeSection();
            return;
        }

        // Parse routes:
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
        const bookMatch = path.match(/^\/books\/([^\/]+)$/);
        const mediumMatch = path.match(/^\/books\/([^\/]+)\/summary$/);
        const chapterMatch = path.match(/^\/books\/([^\/]+)\/chapters\/(\d+)$/);
        const categoryMatch = path.match(/^\/categories\/(\d+)$/);
        const categoriesMatch = path === '/categories';
        const allBooksMatch = path === '/books';
        const discoverMatch = path === '/discover';
        const authorMatch = path.match(/^\/authors\/(.+)$/);
        const blogMatch = path === '/blog';
        const blogPostMatch = path.match(/^\/blog\/([^\/]+)$/);

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

    updateURL(book, page = null) {
        // Use slug from backend if available, fallback to generating from title
        const slug = book.slug || this.slugify(book.title);
        let newPath = `/books/${slug}`;

        if (page === 'summary') {
            newPath = `/books/${slug}/summary`;
        } else if (typeof page === 'number') {
            newPath = `/books/${slug}/chapters/${page}`;
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

    setupPersistentPlayer() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const playPauseBtn = document.getElementById('player-play-pause');
        const stopBtn = document.getElementById('player-stop');
        const progressBar = document.querySelector('.progress-bar');
        const progressFill = document.getElementById('progress-fill');
        const currentTimeSpan = document.getElementById('current-time');
        const totalTimeSpan = document.getElementById('total-time');

        playPauseBtn.addEventListener('click', () => {
            if (persistentAudio.paused) {
                persistentAudio.play();
                playPauseBtn.textContent = '⏸';
                this.currentPlayback.isPlaying = true;
            } else {
                persistentAudio.pause();
                playPauseBtn.textContent = '▶';
                this.currentPlayback.isPlaying = false;
            }
        });

        stopBtn.addEventListener('click', () => {
            this.stopPlayback();
        });

        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            persistentAudio.currentTime = percent * persistentAudio.duration;
        });

        persistentAudio.addEventListener('timeupdate', () => {
            if (persistentAudio.duration) {
                const percent = (persistentAudio.currentTime / persistentAudio.duration) * 100;
                progressFill.style.width = `${percent}%`;
                currentTimeSpan.textContent = this.formatTime(persistentAudio.currentTime);
                totalTimeSpan.textContent = this.formatTime(persistentAudio.duration);
            }
        });

        persistentAudio.addEventListener('ended', () => {
            this.handleAudioEnded();
        });

        persistentAudio.addEventListener('loadedmetadata', () => {
            totalTimeSpan.textContent = this.formatTime(persistentAudio.duration);
        });
    }

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    async stopPlayback() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const persistentPlayer = document.getElementById('persistent-player');
        const playPauseBtn = document.getElementById('player-play-pause');

        persistentAudio.pause();
        persistentAudio.currentTime = 0;
        persistentAudio.src = '';

        const audioIdToCleanup = this.currentPlayback.audioId;

        this.currentPlayback = {
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null
        };

        persistentPlayer.classList.add('hidden');
        playPauseBtn.textContent = '▶';

        try {
            await fetch(`${this.apiBase}/tts/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ audio_id: audioIdToCleanup })
            });
        } catch (error) {
            console.error('Error stopping TTS:', error);
        }
    }

    async handleAudioEnded() {
        this.currentPlayback.currentChunk++;
        if (this.currentPlayback.currentChunk < this.currentPlayback.audioUrls.length) {
            await this.playNextChunk();
        } else {
            const playPauseBtn = document.getElementById('player-play-pause');
            playPauseBtn.textContent = '▶';
            this.currentPlayback.isPlaying = false;

            const audioIdToCleanup = this.currentPlayback.audioId;
            if (audioIdToCleanup) {
                try {
                    await fetch(`${this.apiBase}/tts/stop`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ audio_id: audioIdToCleanup })
                    });
                } catch (error) {
                    console.error('Error cleaning up:', error);
                }
            }
        }
    }

    async playNextChunk() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const chunkUrl = this.currentPlayback.audioUrls[this.currentPlayback.currentChunk];
        const chunkIndex = this.currentPlayback.currentChunk;

        if (chunkIndex > 0) {
            const isReady = await this.waitForChunk(chunkUrl);
            if (!isReady) {
                alert(`Audio playback failed: Chunk ${chunkIndex + 1} could not be loaded.`);
                await this.stopPlayback();
                return;
            }
        }

        persistentAudio.src = chunkUrl;

        // Update MediaSession metadata for Bluetooth/lock screen
        this.updateMediaSessionMetadata();

        try {
            await persistentAudio.play();
            const playPauseBtn = document.getElementById('player-play-pause');
            playPauseBtn.textContent = '⏸';
            this.currentPlayback.isPlaying = true;
        } catch (error) {
            console.error('Error playing chunk:', error);
            alert('Failed to play audio chunk.');
            await this.stopPlayback();
        }
    }

    async waitForChunk(url, retries = 30) {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, { method: 'HEAD' });
                if (response.ok) return true;
            } catch (error) {
                // Chunk not ready yet
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        return false;
    }

    renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        return this.escapeHtml(text).replace(/\n/g, '<br>');
    }

    formatChapterText(text) {
        if (!text) return '';
        const paragraphs = text.split(/\n/);
        return paragraphs
            .filter(p => p.trim().length > 0)
            .map(p => {
                // Escape HTML first to prevent XSS
                let escaped = this.escapeHtml(p.trim());
                // Convert _text_ to <em>text</em> for italic emphasis
                // Match underscores that wrap words (not at word boundaries with spaces)
                escaped = escaped.replace(/\b_([^_]+?)_\b/g, '<em>$1</em>');
                return `<p>${escaped}</p>`;
            })
            .join('');
    }

    formatSideBySideText(originalText, modernText) {
        if (!originalText || !modernText) return '';

        // Split both texts into paragraphs
        const originalParagraphs = originalText.split(/\n/).filter(p => p.trim().length > 0);
        const modernParagraphs = modernText.split(/\n/).filter(p => p.trim().length > 0);

        // Use the longer array length to ensure we don't miss any paragraphs
        const maxLength = Math.max(originalParagraphs.length, modernParagraphs.length);

        // Add headers
        let html = `
            <div class="side-by-side-headers">
                <div class="side-by-side-header">Original</div>
                <div class="side-by-side-header">Modern English</div>
            </div>
        `;

        // Create paired rows - each row contains one original paragraph and one modern paragraph
        for (let i = 0; i < maxLength; i++) {
            // Get paragraph or empty string if index exceeds array length
            const originalPara = originalParagraphs[i] || '';
            const modernPara = modernParagraphs[i] || '';

            // Format original paragraph
            let originalFormatted = '';
            if (originalPara) {
                let escaped = this.escapeHtml(originalPara.trim());
                escaped = escaped.replace(/\b_([^_]+?)_\b/g, '<em>$1</em>');
                originalFormatted = escaped;
            } else {
                originalFormatted = '&nbsp;';
            }

            // Format modern paragraph
            let modernFormatted = '';
            if (modernPara) {
                let escaped = this.escapeHtml(modernPara.trim());
                escaped = escaped.replace(/\b_([^_]+?)_\b/g, '<em>$1</em>');
                modernFormatted = escaped;
            } else {
                modernFormatted = '&nbsp;';
            }

            // Create a row with two columns (original and modern)
            html += `
                <div class="side-by-side-row">
                    <div class="side-by-side-cell original">
                        <p>${originalFormatted}</p>
                    </div>
                    <div class="side-by-side-cell modern">
                        <p>${modernFormatted}</p>
                    </div>
                </div>
            `;
        }

        return html;
    }

    setupEventListeners() {
        // Note: Back buttons have been replaced with breadcrumb navigation
        // Breadcrumbs are updated via updateBreadcrumbs() in each view method

        const headerHomeLink = document.getElementById('header-home-link');
        if (headerHomeLink) {
            headerHomeLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.saveScrollPosition();
                this.showBooksSection();
            });
        }

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

    updateSummaryTTSButton() {
        const ttsBtn = document.getElementById('active-summary-tts-button');
        if (!ttsBtn) return;

        // Determine which tab is active
        const activeTab = document.querySelector('.summary-tab.active');
        if (!activeTab) return;

        const tabName = activeTab.dataset.tab;

        // Update button based on active tab
        if (tabName === '500-word') {
            if (this.conciseSummaryHasAudio) {
                ttsBtn.classList.remove('hidden');
                ttsBtn.onclick = () => this.generateTTS(this.conciseSummaryContent, 'concise', ttsBtn);
            } else {
                ttsBtn.classList.add('hidden');
            }
        } else if (tabName === '2000-word') {
            if (this.mediumSummaryHasAudio) {
                ttsBtn.classList.remove('hidden');
                ttsBtn.onclick = () => this.generateTTS(this.mediumSummaryContent, 'medium', ttsBtn);
            } else {
                ttsBtn.classList.add('hidden');
            }
        }
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
            ? `<a href="/categories/${category.id}" class="view-all-link">View All →</a>`
            : category.id === 'all' && !isDiscoverPage
                ? `<a href="/books" class="view-all-link">View All →</a>`
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
            bookAuthor.innerHTML = `by <a href="/authors/${authorSlug}" class="author-link">${this.escapeHtml(book.author)}</a>`;
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

        // Load summaries, chapters, and related books
        await Promise.all([
            this.loadConciseSummary(),
            this.loadMediumSummary(),
            this.loadChapters(),
            this.loadRelatedBooks()
        ]);

        // Update URL
        this.updateURL(book);

        // Update breadcrumbs
        this.updateBreadcrumbs('book');

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
            bookAuthor.innerHTML = `by <a href="/authors/${authorSlug}" class="author-link">${this.escapeHtml(authorName)}</a>${countryText}`;
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
                                box.className = 'chapter-box indented';

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
                            box.className = 'chapter-box';

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

    showChapterDetailPage(chapterNum) {
        this.updateURL(this.currentBook, chapterNum);
        this.showChapterDetail(this.currentBook, chapterNum);
    }

    async showMediumDetail(book, restoreScroll = false) {
        this.currentBook = book;

        // Save current scroll position before navigating
        this.saveScrollPosition();

        // Set current page key
        const pageKey = `medium_${book.id}`;
        this.setCurrentPage(pageKey);

        // Show only medium detail section
        this.showOnlySections('medium-detail-section');

        // Hide admin edit button (only shown on chapter pages)
        const adminEditBtn = document.getElementById('admin-edit-chapter-btn');
        if (adminEditBtn) {
            adminEditBtn.classList.add('hidden');
        }

        // Update header
        document.getElementById('medium-detail-title').textContent = book.title;
        document.getElementById('medium-detail-subtitle').textContent = `by ${book.author}`;

        // Load or use cached medium summary
        let hasAudio = false;
        if (!this.mediumSummaryContent) {
            try {
                const response = await fetch(`${this.apiBase}/books/${book.id}/summary/medium`);
                const data = await response.json();
                if (data.success && data.summary) {
                    this.mediumSummaryContent = data.summary.content;
                    hasAudio = data.has_audio || false;
                    this.mediumSummaryHasAudio = hasAudio; // Cache the audio flag
                }
            } catch (error) {
                console.error('Error loading medium summary:', error);
            }
        } else {
            // Use cached audio flag
            hasAudio = this.mediumSummaryHasAudio || false;
        }

        const mediumDetailText = document.getElementById('medium-detail-text');
        mediumDetailText.innerHTML = this.renderMarkdown(this.mediumSummaryContent || 'Summary not available');

        // Setup TTS button - only show if audio is available
        const ttsBtn = document.getElementById('medium-detail-tts-button');
        if (hasAudio) {
            ttsBtn.classList.remove('hidden');
            ttsBtn.onclick = () => this.generateTTS(this.mediumSummaryContent, 'medium', ttsBtn);
        } else {
            ttsBtn.classList.add('hidden');
        }

        // Setup sticky header for medium summary
        const stickyMediumBookTitle = document.getElementById('sticky-medium-book-title');
        if (stickyMediumBookTitle) {
            stickyMediumBookTitle.textContent = book.title;
        }

        // Setup reading settings button for medium summary
        const settingsToggleMedium = document.getElementById('reading-settings-toggle-medium');
        const stickySettingsBtnMedium = document.getElementById('sticky-settings-btn-medium');

        if (settingsToggleMedium) {
            settingsToggleMedium.addEventListener('click', () => {
                const panel = document.getElementById('reading-settings-panel');
                if (panel) panel.classList.remove('hidden');
            });
        }

        if (stickySettingsBtnMedium) {
            stickySettingsBtnMedium.addEventListener('click', () => {
                const panel = document.getElementById('reading-settings-panel');
                if (panel) panel.classList.remove('hidden');
            });
        }

        // Setup sticky header scroll detection for medium summary
        this.setupStickyHeaderMedium();

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }

        // Initialize reading progress for medium summary
        setTimeout(() => this.updateReadingProgressMedium(), 100);

        // Update breadcrumbs
        this.updateBreadcrumbs('medium');

        // Update page title
        this.updatePageTitle(`Summary of ${book.title} by ${book.author} | Summra`);
    }

    async showChapterDetail(book, chapterNum, restoreScroll = false) {
        this.currentBook = book;
        this.currentChapter = chapterNum;

        // Save current scroll position before navigating
        this.saveScrollPosition();

        // Set current page key
        const pageKey = `chapter_${book.id}_${chapterNum}`;
        this.setCurrentPage(pageKey);

        // Show only chapter detail section
        this.showOnlySections('chapter-detail-section');

        // Fetch individual chapter data on demand (optimized - only fetches one chapter)
        let chapter = this.chapters.find(c => c.chapter_number === chapterNum);

        // If chapter doesn't have full details (summary/text), fetch them
        if (!chapter || !chapter.summary) {
            // Show loading state only when fetching new data
            const chapterFulltext = document.getElementById('chapter-fulltext');
            const chapterSummaryText = document.getElementById('chapter-summary-text');

            if (chapterFulltext && !restoreScroll) {
                chapterFulltext.innerHTML = `
                    <div class="loading-container">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">Loading chapter text...</div>
                    </div>
                `;
            }

            if (chapterSummaryText && !restoreScroll) {
                chapterSummaryText.innerHTML = `
                    <div class="loading-container" style="min-height: 150px; padding: 2rem;">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">Loading summary...</div>
                    </div>
                `;
            }
            try {
                const response = await fetch(`${this.apiBase}/books/${book.id}/chapters/${chapterNum}`);
                const data = await response.json();
                if (data.success && data.chapter) {
                    // Update the chapter in the chapters array or add it
                    const index = this.chapters.findIndex(c => c.chapter_number === chapterNum);
                    if (index >= 0) {
                        this.chapters[index] = data.chapter;
                    } else {
                        this.chapters.push(data.chapter);
                    }
                    chapter = data.chapter;
                }
            } catch (error) {
                console.error('Error loading chapter details:', error);
            }
        }
        if (!chapter) {
            if (chapterFulltext) {
                chapterFulltext.innerHTML = '<p class="error">Chapter not found</p>';
            }
            return;
        }

        // Update header
        const chapterTitle = chapter.chapter_title || `Chapter ${chapterNum}`;
        document.getElementById('chapter-detail-title').textContent = `${chapterNum}. ${chapterTitle}`;
        document.getElementById('chapter-detail-subtitle').textContent = book.title;

        // Show admin edit button only in development mode
        const adminEditBtn = document.getElementById('admin-edit-chapter-btn');
        if (adminEditBtn) {
            if (window.__IS_DEVELOPMENT__) {
                adminEditBtn.classList.remove('hidden');
            } else {
                adminEditBtn.classList.add('hidden');
            }
        }

        // Display illustration if available
        const illustrationContainer = document.getElementById('chapter-illustration-container');
        const illustrationImg = document.getElementById('chapter-illustration');
        const illustrationWebp = document.getElementById('chapter-illustration-webp');
        const illustrationJpg = document.getElementById('chapter-illustration-jpg');

        if (chapter.illustration_url && chapter.illustration_url.trim() !== '') {
            // Illustration available - show it
            let illustrationUrl = chapter.illustration_url;
            // Convert local path to URL if needed (similar to cover images)
            if (!illustrationUrl.startsWith('http') && !illustrationUrl.startsWith('/static/')) {
                illustrationUrl = `/static/${illustrationUrl}`;
            }

            // Generate optimized image URLs (WebP and JPG)
            // Remove extension from URL and add .webp and .jpg
            const baseUrl = illustrationUrl.replace(/\.(png|jpg|jpeg)$/i, '');
            const webpUrl = `${baseUrl}.webp`;
            const jpgUrl = `${baseUrl}.jpg`;

            // Set picture sources for WebP and JPG
            illustrationWebp.srcset = webpUrl;
            illustrationJpg.srcset = jpgUrl;
            illustrationImg.src = jpgUrl; // Fallback for older browsers
            illustrationImg.alt = `Illustration for ${chapterTitle}`;
            illustrationContainer.classList.remove('hidden');

            // Add click handler to open in lightbox - pass base URL for lightbox to handle formats
            illustrationImg.onclick = () => {
                if (this.openLightbox) {
                    this.openLightbox(baseUrl, `Illustration for ${chapterTitle}`);
                }
            };
        } else {
            // No illustration - hide the container
            illustrationContainer.classList.add('hidden');
        }

        // Load summary (collapsed by default) - hide if no summary available
        const summaryBox = document.getElementById('chapter-summary-box');
        const summaryText = document.getElementById('chapter-summary-text');

        if (!chapter.summary || chapter.summary.trim() === '') {
            // No summary available - hide the summary box (short chapters below MIN_CHAPTER_WORDS)
            summaryBox.style.display = 'none';
        } else {
            // Summary available - show and populate
            summaryBox.style.display = '';
            summaryText.innerHTML = this.renderMarkdown(chapter.summary);

            // Setup toggle - make entire summary box clickable
            const toggleBtn = document.getElementById('toggle-summary-btn');
            const summaryHeader = document.getElementById('chapter-summary-header');
            const summaryContent = document.getElementById('chapter-summary-content');
            let isSummaryExpanded = false;

            const toggleSummary = (e) => {
                // Don't toggle if clicking on TTS button
                if (e && e.target.closest('.tts-button-inline')) {
                    return;
                }

                if (isSummaryExpanded) {
                    summaryContent.classList.add('hidden');
                    toggleBtn.textContent = '▼';
                    summaryBox.classList.add('collapsed');
                    isSummaryExpanded = false;
                } else {
                    summaryContent.classList.remove('hidden');
                    toggleBtn.textContent = '▲';
                    summaryBox.classList.remove('collapsed');
                    isSummaryExpanded = true;
                }
            };

            // Make entire header clickable (including chevron area)
            summaryHeader.style.cursor = 'pointer';
            summaryHeader.onclick = toggleSummary;

            // Remove separate onclick from button to prevent event conflicts
            // The button will be toggled via the header click
            toggleBtn.style.pointerEvents = 'none';

            // Setup summary TTS button - only show if audio is available
            const summaryTtsBtn = document.getElementById('chapter-summary-tts-button');
            if (chapter.has_audio) {
                summaryTtsBtn.classList.remove('hidden');
                summaryTtsBtn.onclick = () => {
                    this.generateChapterTTS(chapterNum, chapter.summary, summaryTtsBtn, 'summary');
                };
            } else {
                summaryTtsBtn.classList.add('hidden');
            }
        }

        // Load full text
        const fullTextEl = document.getElementById('chapter-fulltext');
        if (chapter.chapter_text) {
            fullTextEl.innerHTML = this.formatChapterText(chapter.chapter_text);
        } else {
            fullTextEl.innerHTML = '<p class="error">Full text not available for this chapter</p>';
        }

        // Handle modern English view mode toggle
        const viewModeToggle = document.getElementById('view-mode-toggle');
        const modernEnglishEl = document.getElementById('chapter-modern-english');
        const sideBySideEl = document.getElementById('chapter-side-by-side');

        if (chapter.modern_english_text) {
            // Modern English is available - show view mode toggle
            viewModeToggle.classList.remove('hidden');

            // Populate modern English container
            modernEnglishEl.innerHTML = this.formatChapterText(chapter.modern_english_text);

            // Populate side-by-side container with aligned paragraph rows
            const sideBySideFormatted = this.formatSideBySideText(
                chapter.chapter_text,
                chapter.modern_english_text
            );
            sideBySideEl.innerHTML = sideBySideFormatted;

            // Function to check if screen is too narrow for side-by-side view
            const isScreenTooNarrow = () => window.innerWidth < 1024;

            // Load saved view mode preference or default to original
            const savedViewMode = localStorage.getItem('reading_chapterViewMode') || 'original';

            // Apply saved view mode (unless it's side-by-side on narrow screen)
            let viewModeToApply = savedViewMode;
            if (savedViewMode === 'side-by-side' && isScreenTooNarrow()) {
                viewModeToApply = 'original';
            }

            // Set initial view based on saved preference
            fullTextEl.classList.toggle('hidden', viewModeToApply !== 'original');
            modernEnglishEl.classList.toggle('hidden', viewModeToApply !== 'modern');
            sideBySideEl.classList.toggle('hidden', viewModeToApply !== 'side-by-side');

            // Setup view mode toggle event listeners
            const viewModeBtns = document.querySelectorAll('.view-mode-btn');

            // Set active button based on applied view mode
            viewModeBtns.forEach(btn => {
                if (btn.dataset.mode === viewModeToApply) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Function to update side-by-side button visibility based on screen width
            const updateSideBySideButtonVisibility = () => {
                const sideBySideBtn = document.querySelector('.view-mode-btn[data-mode="side-by-side"]');
                if (sideBySideBtn) {
                    if (isScreenTooNarrow()) {
                        sideBySideBtn.style.display = 'none';

                        // If currently viewing side-by-side, switch to original view
                        if (!sideBySideEl.classList.contains('hidden')) {
                            const originalBtn = document.querySelector('.view-mode-btn[data-mode="original"]');
                            if (originalBtn) {
                                viewModeBtns.forEach(b => b.classList.remove('active'));
                                originalBtn.classList.add('active');
                                fullTextEl.classList.remove('hidden');
                                modernEnglishEl.classList.add('hidden');
                                sideBySideEl.classList.add('hidden');
                            }
                        }
                    } else {
                        sideBySideBtn.style.display = '';
                    }
                }
            };

            // Initial check
            updateSideBySideButtonVisibility();

            // Update on resize
            window.addEventListener('resize', updateSideBySideButtonVisibility);

            viewModeBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const mode = btn.dataset.mode;

                    // Check if trying to view side-by-side on narrow screen
                    if (mode === 'side-by-side' && isScreenTooNarrow()) {
                        alert('Side-by-side view requires a wider screen. Please expand your browser window or use a larger device.');
                        return;
                    }

                    // Update active button
                    viewModeBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Show/hide appropriate containers
                    fullTextEl.classList.toggle('hidden', mode !== 'original');
                    modernEnglishEl.classList.toggle('hidden', mode !== 'modern');
                    sideBySideEl.classList.toggle('hidden', mode !== 'side-by-side');

                    // Save view mode preference
                    this.saveReadingPreference('chapterViewMode', mode);
                });
            });
        } else {
            // No modern English - hide toggle and show only original text
            viewModeToggle.classList.add('hidden');
            fullTextEl.classList.remove('hidden');
            modernEnglishEl.classList.add('hidden');
            sideBySideEl.classList.add('hidden');
        }

        // Setup fulltext TTS button - only show if audio is available
        const fulltextTtsBtn = document.getElementById('chapter-fulltext-tts-button');
        if (chapter.chapter_text && chapter.has_audio) {
            fulltextTtsBtn.classList.remove('hidden');
            fulltextTtsBtn.onclick = () => {
                this.generateChapterTTS(chapterNum, chapter.chapter_text, fulltextTtsBtn, 'fulltext');
            };
        } else {
            fulltextTtsBtn.classList.add('hidden');
        }

        // Setup next chapter button
        this.setupNextChapterButton(chapterNum);

        // Update sticky header title with chapter and book name
        this.updateStickyHeaderTitle(book.title, chapterNum, chapterTitle);

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }

        // Initialize reading progress
        setTimeout(() => this.updateReadingProgress(), 100);

        // Update breadcrumbs
        this.updateBreadcrumbs('chapter');

        // Update page title
        this.updatePageTitle(`Full Text of ${chapterTitle} - ${book.title} | Summra`);
    }

    async generateTTS(text, type, buttonElement) {
        if (!text) {
            alert('No text available');
            return;
        }

        const cleanedText = this.cleanTextForTTS(text);
        buttonElement.disabled = true;
        buttonElement.textContent = '🔄 Loading...';

        try {
            const audioId = `book_${this.currentBook.id}_${type}`;
            const textToSend = this.truncateAtSentenceBoundary(cleanedText, 5000);

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                const audioUrls = data.streaming && data.audio_urls ? data.audio_urls : [data.audio_url];
                // Use better labels for lock screen display: "Quick Summary" or "Full Summary"
                const displayType = type === 'concise' ? 'Quick Summary' : 'Full Summary';
                this.startPersistentPlayback(
                    audioUrls,
                    this.currentBook.title,
                    displayType,
                    data.audio_id,
                    this.currentBook.author
                );
                buttonElement.disabled = false;
                buttonElement.textContent = '🔊 Listen';
            } else {
                alert(`Error generating audio: ${data.error}`);
                buttonElement.textContent = '🔊 Listen';
                buttonElement.disabled = false;
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
            buttonElement.textContent = '🔊 Listen';
            buttonElement.disabled = false;
        }
    }

    async generateChapterTTS(chapterNumber, text, buttonElement, contentType = 'summary') {
        if (!text) {
            alert('No text available');
            return;
        }

        const originalText = buttonElement.textContent;
        buttonElement.disabled = true;
        buttonElement.textContent = '⏳ Loading...';

        const cleanedText = this.cleanTextForTTS(text);
        const audioId = `book_${this.currentBook.id}_chapter_${chapterNumber}_${contentType}`;
        const chapterTitle = `Chapter ${chapterNumber}`;

        try {
            const maxChars = contentType === 'fulltext' ? 20000 : 5000;
            const textToSend = this.truncateAtSentenceBoundary(cleanedText, maxChars);

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                const audioUrls = data.streaming && data.audio_urls ? data.audio_urls : [data.audio_url];
                this.startPersistentPlayback(
                    audioUrls,
                    this.currentBook.title,
                    chapterTitle,
                    data.audio_id,
                    this.currentBook.author
                );
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            } else {
                alert(`Error generating audio: ${data.error}`);
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
            buttonElement.textContent = originalText;
            buttonElement.disabled = false;
        }
    }

    updatePlayerInfo(bookTitle, chapterTitle) {
        document.getElementById('player-title').textContent = bookTitle;
        document.getElementById('player-subtitle').textContent = chapterTitle;
    }

    updateMediaSessionMetadata() {
        // Update MediaSession API for Bluetooth/CarPlay/Android Auto/lock screen
        if ('mediaSession' in navigator && this.currentPlayback) {
            const bookTitle = this.currentPlayback.bookTitle || 'Unknown Book';
            const chapterTitle = this.currentPlayback.chapterTitle || 'Summary';
            const author = this.currentPlayback.author || 'Unknown Author';

            // Get book cover URL if available
            const coverUrl = this.currentBook && this.currentBook.cover_image_url
                ? window.location.origin + this.currentBook.cover_image_url
                : null;

            // Format: Title = "{book name} by {author name}", Artist = "Quick Summary" or "Full Summary" or "Chapter X"
            const displayTitle = `${bookTitle} by ${author}`;

            // Set metadata
            navigator.mediaSession.metadata = new MediaMetadata({
                title: displayTitle,
                artist: chapterTitle,
                album: 'Summra Audiobook Summaries',
                artwork: coverUrl ? [
                    { src: coverUrl, sizes: '512x512', type: 'image/jpeg' },
                    { src: coverUrl, sizes: '256x256', type: 'image/jpeg' },
                    { src: coverUrl, sizes: '128x128', type: 'image/jpeg' }
                ] : []
            });

            // Set up playback controls
            navigator.mediaSession.setActionHandler('play', () => {
                const playPauseBtn = document.getElementById('player-play-pause');
                if (playPauseBtn) playPauseBtn.click();
            });

            navigator.mediaSession.setActionHandler('pause', () => {
                const playPauseBtn = document.getElementById('player-play-pause');
                if (playPauseBtn) playPauseBtn.click();
            });

            navigator.mediaSession.setActionHandler('stop', () => {
                this.stopPlayback();
            });

            // Previous/Next track handlers (if multi-chunk)
            if (this.currentPlayback.audioUrls && this.currentPlayback.audioUrls.length > 1) {
                navigator.mediaSession.setActionHandler('previoustrack', () => {
                    if (this.currentPlayback.currentChunk > 0) {
                        this.currentPlayback.currentChunk--;
                        this.playNextChunk();
                    }
                });

                navigator.mediaSession.setActionHandler('nexttrack', () => {
                    if (this.currentPlayback.currentChunk < this.currentPlayback.audioUrls.length - 1) {
                        this.currentPlayback.currentChunk++;
                        this.playNextChunk();
                    }
                });
            }
        }
    }

    async startPersistentPlayback(audioUrls, bookTitle, chapterTitle, audioId = null, author = null) {
        const persistentPlayer = document.getElementById('persistent-player');

        this.currentPlayback = {
            isPlaying: true,
            currentChunk: 0,
            audioUrls: audioUrls,
            bookTitle: bookTitle,
            chapterTitle: chapterTitle,
            audioId: audioId,
            author: author
        };

        this.updatePlayerInfo(bookTitle, chapterTitle);
        persistentPlayer.classList.remove('hidden');
        await this.playNextChunk();
    }

    truncateAtSentenceBoundary(text, maxChars = 5000) {
        if (text.length <= maxChars) return text;

        let truncated = text.substring(0, maxChars);
        const sentenceEndPattern = /[.!?][\s]/g;
        let lastMatch = null;
        let match;

        while ((match = sentenceEndPattern.exec(truncated)) !== null) {
            lastMatch = match;
        }

        if (lastMatch) {
            truncated = truncated.substring(0, lastMatch.index + 2);
        } else {
            const lastSpace = truncated.lastIndexOf(' ');
            if (lastSpace > maxChars * 0.8) {
                truncated = truncated.substring(0, lastSpace);
            }
        }

        return truncated.trim();
    }

    cleanTextForTTS(text) {
        let cleaned = text;
        cleaned = cleaned.replace(/[""]/g, '"');
        cleaned = cleaned.replace(/['']/g, "'");
        cleaned = cleaned.replace(/[«»]/g, '"');
        cleaned = cleaned.replace(/…/g, '...');
        cleaned = cleaned.replace(/^#{1,6}\s+/gm, '');
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
        cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
        cleaned = cleaned.replace(/_([^_]+)_/g, '$1');
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
        cleaned = cleaned.replace(/^>\s+/gm, '');
        cleaned = cleaned.replace(/^[\-*_]{3,}\s*$/gm, '');
        cleaned = cleaned.replace(/^[\s]*[-*+]\s+/gm, '');
        cleaned = cleaned.replace(/^[\s]*\d+\.\s+/gm, '');
        cleaned = cleaned.replace(/<[^>]+>/g, '');
        cleaned = cleaned.replace(/[\[\]{}]/g, '');
        cleaned = cleaned.replace(/!+/g, '!');
        cleaned = cleaned.replace(/\?+/g, '?');
        cleaned = cleaned.replace(/\.{4,}/g, '...');
        cleaned = cleaned.replace(/[\u200B-\u200D\uFEFF]/g, '');
        cleaned = cleaned.replace(/\s+/g, ' ');
        cleaned = cleaned.replace(/\n+/g, ' ');
        cleaned = cleaned.replace(/[?!]{2,}/g, '!');
        cleaned = cleaned.trim();

        if (cleaned && !cleaned.match(/[.!?]$/)) {
            cleaned = cleaned + '.';
        }

        return cleaned;
    }

    async showHomeSection() {
        this.saveScrollPosition();
        this.setCurrentPage('home');
        this.currentView = 'home';

        // Check if hero section has content (not just a placeholder)
        const heroSection = document.getElementById('hero-section');
        const isPlaceholder = heroSection && heroSection.classList.contains('hidden') && heroSection.children.length === 0;

        // If hero section is just a placeholder (from blog/book pages), render it dynamically
        // instead of doing a full page reload (which would stop audio playback)
        if (isPlaceholder) {
            // Render hero section content dynamically
            heroSection.innerHTML = `
                <!-- Main Hero Banner -->
                <section class="hero-banner hero-main">
                    <div class="hero-banner-content">
                        <h1 class="hero-banner-title">Classic Literature, Made&nbsp;Easy</h1>
                        <p class="hero-banner-subtitle">Reading companion that makes you enjoy reading.</p>
                        <div class="hero-search-container">
                            <div class="hero-search-wrapper">
                                <input type="text"
                                       class="hero-search-input"
                                       id="hero-search-input"
                                       placeholder="Search for a book or author..."
                                       autocomplete="off">
                                <div class="hero-search-results hidden" id="hero-search-results">
                                    <!-- Typeahead results will be populated here -->
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <!-- Discover Banner -->
                <section class="hero-banner hero-discover">
                    <div class="hero-banner-content">
                        <h2 class="hero-banner-heading">Discover Classics the&nbsp;Modern&nbsp;Way</h2>
                    </div>

                    <!-- Top 10 Books Carousel (direct child of section, breaks out on mobile) -->
                    <div class="top-10-carousel-wrapper">
                        <div class="carousel-container top-10-carousel">
                            <button class="carousel-nav-btn left" id="top-10-nav-left">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M15 18l-6-6 6-6"></path>
                                </svg>
                            </button>
                            <div class="carousel-scroll" id="top-10-scroll">
                                <!-- Loading skeleton cards (will be replaced when books load) -->
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                                <div class="skeleton-book-card"></div>
                            </div>
                            <button class="carousel-nav-btn right" id="top-10-nav-right">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M9 18l6-6-6-6"></path>
                                </svg>
                            </button>
                        </div>
                    </div>

                    <div class="hero-banner-content">
                        <div class="hero-banner-ctas">
                            <a href="javascript:void(0)" class="hero-cta-primary" data-route="discover">Explore Classics</a>
                            <a href="javascript:void(0)" class="hero-cta-secondary" data-route="books">Browse All Books</a>
                        </div>
                    </div>
                </section>

                <!-- Learn Banner -->
                <section class="hero-banner hero-learn">
                    <div class="hero-banner-content">
                        <h2 class="hero-banner-heading">Literature, Beautifully&nbsp;Explained</h2>

                        <!-- 3-Column Features Grid -->
                        <div class="learn-features-grid">
                            <!-- Column 1: Beautiful Illustrations -->
                            <div class="learn-feature-card">
                                <div class="learn-feature-icon">
                                    <picture>
                                        <source srcset="/static/images/infographic.webp" type="image/webp">
                                        <source srcset="/static/images/infographic.jpg" type="image/jpeg">
                                        <img src="/static/images/infographic.jpg" alt="Visual guides with color and interactivity" class="learn-feature-image">
                                    </picture>
                                </div>
                                <h3 class="learn-feature-title">Beautiful Illustrations</h3>
                                <p class="learn-feature-description">Make sense of complex plots and symbolism with beautifully illustrated character maps, timelines, and theme guides.</p>
                            </div>

                            <!-- Column 2: Audio Summary -->
                            <div class="learn-feature-card">
                                <div class="learn-feature-icon">
                                    <picture>
                                        <source srcset="/static/images/summary.webp" type="image/webp">
                                        <source srcset="/static/images/summary.jpg" type="image/jpeg">
                                        <img src="/static/images/summary.jpg" alt="Comprehensive book summaries" class="learn-feature-image">
                                    </picture>
                                </div>
                                <h3 class="learn-feature-title">Audio Summary</h3>
                                <p class="learn-feature-description">Help you preview, understand, and enjoy classics at your own pace.</p>
                            </div>

                            <!-- Column 3: For Every Reader -->
                            <div class="learn-feature-card">
                                <div class="learn-feature-icon">
                                    <picture>
                                        <source srcset="/static/images/chapter_view.webp" type="image/webp">
                                        <source srcset="/static/images/chapter_view.jpg" type="image/jpeg">
                                        <img src="/static/images/chapter_view.jpg" alt="Accessible reading experience" class="learn-feature-image">
                                    </picture>
                                </div>
                                <h3 class="learn-feature-title">For Every Reader</h3>
                                <p class="learn-feature-description">Kindle-like reading experience enhanced with chapter illustrations, summaries and plain-English version for English learners.</p>
                            </div>
                        </div>

                        <div class="hero-banner-ctas">
                            <a href="javascript:void(0)" class="hero-cta-primary" data-route="books/jane-eyre">See Example: Jane Eyre</a>
                        </div>
                    </div>
                </section>
            `;

            // Re-initialize hero search after rendering
            if (window.heroSearchInstance) {
                // Re-query DOM elements in case they changed
                window.heroSearchInstance.searchInput = document.getElementById('hero-search-input');
                window.heroSearchInstance.searchResults = document.getElementById('hero-search-results');
                if (window.heroSearchInstance.searchInput && window.heroSearchInstance.searchResults) {
                    window.heroSearchInstance.init();
                }
            } else {
                window.heroSearchInstance = new HeroSearch();
            }

            // Re-attach hero banner CTA listeners
            const heroCtas = heroSection.querySelectorAll('[data-route]');
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
                    window.history.pushState(null, '', `/${route}`);
                    this.handleRoute();
                });
            });
        }

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

        // Update breadcrumbs
        this.updateBreadcrumbs('category');

        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }

        // Update page title
        if (categoryData && categoryData.category) {
            this.updatePageTitle(`${categoryData.category.name} - Classic Books | Summra`);
        }
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

        // Update breadcrumbs
        this.updateBreadcrumbs('all-categories');

        if (restoreScroll) {
            this.restoreScrollPosition('all-categories');
        } else {
            window.scrollTo(0, 0);
        }

        // Update page title
        this.updatePageTitle('Browse Categories - Classic Book Summaries | Summra');
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

        // Render all books in grid
        const grid = document.getElementById('category-books-grid');
        grid.innerHTML = '';
        this.allBooks.forEach(book => {
            const bookCard = this.createBookCard(book);
            grid.appendChild(bookCard);
        });

        // Update breadcrumbs for All Books page
        this.updateBreadcrumbs('category');

        if (restoreScroll) {
            this.restoreScrollPosition('all-books');
        } else {
            window.scrollTo(0, 0);
        }

        // Update page title
        this.updatePageTitle('Browse Classic Books - Free Summaries | Summra');
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
                fetch(`/api/authors/${authorSlug}`),
                fetch(`/api/authors/${authorSlug}/books`)
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
            const response = await fetch('/api/discover/carousels');
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
                    <button onclick="window.location.href='/'">Go Home</button>
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

    createBookCard(book) {
        const bookCard = document.createElement('div');
        bookCard.className = 'book-card';

        const coverImageHtml = book.cover_image_url
            ? this.getImageHtml(book.cover_image_url, `${book.title} cover`, 'book-cover')
            : '';

        bookCard.innerHTML = `
            ${coverImageHtml}
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

        // Update breadcrumbs
        this.updateBreadcrumbs('blog');

        // Update page title
        this.updatePageTitle('Blog - Classic Literature Guides | Summra');

        if (restoreScroll) {
            this.restoreScrollPosition('blog');
        } else {
            window.scrollTo(0, 0);
        }
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

        // Update breadcrumbs
        this.updateBreadcrumbs('blog-post');

        // Update page title (will be updated by BlogPost component with actual title)
        this.updatePageTitle('Blog Post | Summra');

        if (restoreScroll) {
            this.restoreScrollPosition(`blog-post-${slug}`);
        } else {
            window.scrollTo(0, 0);
        }
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

    // ===== Reading Experience Features =====

    setupReadingSettings() {
        // Settings panel toggle
        const toggleBtn = document.getElementById('reading-settings-toggle');
        const stickyToggleBtn = document.getElementById('sticky-settings-btn');
        const panel = document.getElementById('reading-settings-panel');
        const closeBtn = document.getElementById('reading-settings-close');

        const openPanel = () => {
            if (panel) panel.classList.remove('hidden');
        };

        const closePanel = () => {
            if (panel) panel.classList.add('hidden');
        };

        if (toggleBtn) {
            toggleBtn.addEventListener('click', openPanel);
        }

        if (stickyToggleBtn) {
            stickyToggleBtn.addEventListener('click', openPanel);
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        // Handle sticky header visibility
        this.setupStickyHeader();

        // Font selection
        const fontChoices = document.querySelectorAll('.font-choice');
        fontChoices.forEach(btn => {
            btn.addEventListener('click', () => {
                fontChoices.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const font = btn.dataset.font;
                this.applyFont(font);
                this.saveReadingPreference('font', font);
            });
        });

        // Font size controls
        const slider = document.getElementById('font-size-slider');
        const decreaseBtn = document.getElementById('decrease-size');
        const increaseBtn = document.getElementById('increase-size');
        const sizeValue = document.getElementById('size-value');

        if (slider) {
            slider.addEventListener('input', (e) => {
                const size = e.target.value;
                this.applyFontSize(size);
                sizeValue.textContent = `${size}px`;
                this.saveReadingPreference('fontSize', size);
            });
        }

        if (decreaseBtn) {
            decreaseBtn.addEventListener('click', () => {
                const currentSize = parseInt(slider.value);
                const newSize = Math.max(12, currentSize - 1);
                slider.value = newSize;
                this.applyFontSize(newSize);
                sizeValue.textContent = `${newSize}px`;
                this.saveReadingPreference('fontSize', newSize);
            });
        }

        if (increaseBtn) {
            increaseBtn.addEventListener('click', () => {
                const currentSize = parseInt(slider.value);
                const newSize = Math.min(24, currentSize + 1);
                slider.value = newSize;
                this.applyFontSize(newSize);
                sizeValue.textContent = `${newSize}px`;
                this.saveReadingPreference('fontSize', newSize);
            });
        }

        // Theme selection
        const themeChoices = document.querySelectorAll('.theme-choice');
        themeChoices.forEach(btn => {
            btn.addEventListener('click', () => {
                themeChoices.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const theme = btn.dataset.theme;
                this.applyTheme(theme);
                this.saveReadingPreference('theme', theme);
            });
        });

        // Reading progress tracking
        window.addEventListener('scroll', () => {
            this.updateReadingProgress();
            this.updateReadingProgressMedium();
        });
    }

    applyFont(font) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');
        if (chapterSection) {
            chapterSection.setAttribute('data-font', font);
        }
        if (mediumSection) {
            mediumSection.setAttribute('data-font', font);
        }
    }

    applyFontSize(size) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');

        if (chapterSection) {
            const fulltext = chapterSection.querySelector('.chapter-fulltext');
            const modernEnglish = chapterSection.querySelector('.chapter-modern-english');
            const sideBySideCells = chapterSection.querySelectorAll('.side-by-side-cell');
            const summaryText = chapterSection.querySelector('.chapter-summary-text');
            const summaryContentText = chapterSection.querySelector('#chapter-summary-content .summary-text');

            if (fulltext) fulltext.style.fontSize = `${size}px`;
            if (modernEnglish) modernEnglish.style.fontSize = `${size}px`;
            if (sideBySideCells.length > 0) {
                sideBySideCells.forEach(cell => {
                    cell.style.fontSize = `${size}px`;
                });
            }
            if (summaryText) summaryText.style.fontSize = `${size}px`;
            if (summaryContentText) summaryContentText.style.fontSize = `${size}px`;
        }

        if (mediumSection) {
            const mediumText = mediumSection.querySelector('.summary-text');
            if (mediumText) mediumText.style.fontSize = `${size}px`;
        }
    }

    applyTheme(theme) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');
        if (chapterSection) {
            chapterSection.setAttribute('data-theme', theme);
        }
        if (mediumSection) {
            mediumSection.setAttribute('data-theme', theme);
        }
    }

    saveReadingPreference(key, value) {
        try {
            localStorage.setItem(`reading_${key}`, value);
        } catch (error) {
            console.error('Error saving reading preference:', error);
        }
    }

    loadReadingPreferences() {
        try {
            const font = localStorage.getItem('reading_font') || 'georgia';
            const fontSize = localStorage.getItem('reading_fontSize') || '16';
            const theme = localStorage.getItem('reading_theme') || 'light';

            // Update UI to reflect saved preferences
            const fontBtn = document.querySelector(`.font-choice[data-font="${font}"]`);
            if (fontBtn) {
                document.querySelectorAll('.font-choice').forEach(b => b.classList.remove('active'));
                fontBtn.classList.add('active');
            }

            const slider = document.getElementById('font-size-slider');
            const sizeValue = document.getElementById('size-value');
            if (slider) {
                slider.value = fontSize;
                sizeValue.textContent = `${fontSize}px`;
            }

            const themeBtn = document.querySelector(`.theme-choice[data-theme="${theme}"]`);
            if (themeBtn) {
                document.querySelectorAll('.theme-choice').forEach(b => b.classList.remove('active'));
                themeBtn.classList.add('active');
            }

            // Apply preferences
            this.applyFont(font);
            this.applyFontSize(fontSize);
            this.applyTheme(theme);
        } catch (error) {
            console.error('Error loading reading preferences:', error);
        }
    }

    updateReadingProgress() {
        const chapterSection = document.getElementById('chapter-detail-section');
        if (!chapterSection || chapterSection.classList.contains('hidden')) {
            return;
        }

        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        const scrollTop = window.scrollY;
        const scrollableHeight = documentHeight - windowHeight;

        let progress = 0;
        if (scrollableHeight > 0) {
            progress = Math.min(100, Math.round((scrollTop / scrollableHeight) * 100));
        }

        const progressFill = document.getElementById('reading-progress-fill');
        const progressText = document.getElementById('reading-progress-text');

        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        if (progressText) {
            progressText.textContent = `${progress}%`;
        }
    }

    setupNextChapterButton(currentChapterNum) {
        const nextChapterBtn = document.getElementById('next-chapter-btn');
        if (!nextChapterBtn) {
            console.warn('Next chapter button element not found');
            return;
        }

        // Find the next chapter
        const nextChapter = this.chapters.find(ch => ch.chapter_number === currentChapterNum + 1);

        console.log(`[Next Chapter Button] Current chapter: ${currentChapterNum}`);
        console.log(`[Next Chapter Button] Total chapters loaded: ${this.chapters.length}`);
        console.log(`[Next Chapter Button] Next chapter found:`, nextChapter ? nextChapter.chapter_number : 'none');
        console.log(`[Next Chapter Button] Button element classes before:`, nextChapterBtn.className);

        if (nextChapter) {
            nextChapterBtn.classList.remove('hidden');
            nextChapterBtn.onclick = () => {
                this.showChapterDetailPage(nextChapter.chapter_number);
            };
            console.log(`[Next Chapter Button] Button element classes after (should be visible):`, nextChapterBtn.className);
            console.log(`[Next Chapter Button] Button computed display:`, window.getComputedStyle(nextChapterBtn).display);
        } else {
            nextChapterBtn.classList.add('hidden');
            console.log(`[Next Chapter Button] Button hidden (no next chapter)`);
        }
    }

    setupStickyHeader() {
        let lastScrollTop = 0;
        const stickyHeader = document.getElementById('sticky-reading-header');
        const chapterHeader = document.querySelector('.chapter-detail-header');

        window.addEventListener('scroll', () => {
            const chapterSection = document.getElementById('chapter-detail-section');
            if (!chapterSection || chapterSection.classList.contains('hidden')) {
                return;
            }

            if (!chapterHeader || !stickyHeader) return;

            const scrollTop = window.scrollY;
            const headerBottom = chapterHeader.offsetTop + chapterHeader.offsetHeight;

            // Show sticky header when scrolled past the main chapter header
            if (scrollTop > headerBottom) {
                stickyHeader.classList.remove('hidden');
            } else {
                stickyHeader.classList.add('hidden');
            }

            lastScrollTop = scrollTop;
        });
    }

    updateStickyHeaderTitle(bookTitle, chapterNum = null, chapterTitle = '') {
        const stickyBookTitle = document.getElementById('sticky-book-title');
        const stickyChapterTitle = document.getElementById('sticky-chapter-title');

        if (stickyBookTitle) {
            stickyBookTitle.textContent = bookTitle;
        }
        if (stickyChapterTitle) {
            // Format as "X: Title" or just "X" if no title (without the word "Chapter")
            const displayText = chapterNum
                ? (chapterTitle ? `${chapterNum}: ${chapterTitle}` : `${chapterNum}`)
                : chapterTitle;
            stickyChapterTitle.textContent = displayText;
        }
    }

    setupStickyHeaderMedium() {
        const stickyHeader = document.getElementById('sticky-reading-header-medium');
        const mediumHeader = document.querySelector('.medium-detail-header');

        window.addEventListener('scroll', () => {
            const mediumSection = document.getElementById('medium-detail-section');
            if (!mediumSection || mediumSection.classList.contains('hidden')) {
                return;
            }

            if (!mediumHeader || !stickyHeader) return;

            const scrollTop = window.scrollY;
            const headerBottom = mediumHeader.offsetTop + mediumHeader.offsetHeight;

            if (scrollTop > headerBottom) {
                stickyHeader.classList.remove('hidden');
            } else {
                stickyHeader.classList.add('hidden');
            }
        });
    }

    updateReadingProgressMedium() {
        const mediumSection = document.getElementById('medium-detail-section');
        if (!mediumSection || mediumSection.classList.contains('hidden')) {
            return;
        }

        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        const scrollTop = window.scrollY;
        const scrollableHeight = documentHeight - windowHeight;

        let progress = 0;
        if (scrollableHeight > 0) {
            progress = Math.min(100, Math.round((scrollTop / scrollableHeight) * 100));
        }

        const progressFill = document.getElementById('reading-progress-fill-medium');
        const progressText = document.getElementById('reading-progress-text-medium');

        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        if (progressText) {
            progressText.textContent = `${progress}%`;
        }
    }

    /**
     * Build breadcrumbs based on current view
     */
    buildBreadcrumbs() {
        const breadcrumbs = [
            { name: 'Home', url: '/', position: 1 }
        ];

        const path = window.location.pathname;

        // Parse different page types
        const bookMatch = path.match(/^\/books\/([^\/]+)$/);
        const summaryMatch = path.match(/^\/books\/([^\/]+)\/summary$/);
        const chapterMatch = path.match(/^\/books\/([^\/]+)\/chapters\/(\d+)$/);
        const categoryMatch = path.match(/^\/categories\/(\d+)$/);
        const categoriesMatch = path === '/categories';
        const allBooksMatch = path === '/books';
        const discoverMatch = path === '/discover';
        const blogMatch = path === '/blog';
        const blogPostMatch = path.match(/^\/blog\/([^\/]+)$/);
        const authorMatch = path.match(/^\/authors\/([^\/]+)$/);

        if (discoverMatch) {
            breadcrumbs.push({ name: 'Discover', url: '/discover', position: 2 });
        } else if (authorMatch) {
            const authorName = this.currentAuthor?.name || decodeURIComponent(authorMatch[1]).replace(/-/g, ' ');
            breadcrumbs.push({ name: authorName, url: path, position: 2 });
        } else if (blogPostMatch) {
            breadcrumbs.push({ name: 'Blog', url: '/blog', position: 2 });
            const postName = this.currentBlogPost?.title || 'Post';
            breadcrumbs.push({ name: postName, url: path, position: 3 });
        } else if (blogMatch) {
            breadcrumbs.push({ name: 'Blog', url: '/blog', position: 2 });
        } else if (categoriesMatch) {
            breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
        } else if (categoryMatch) {
            breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
            // Get category name from current data if available
            const categoryId = parseInt(categoryMatch[1]);
            const categoryName = this.currentCategory?.name || `Category ${categoryId}`; // Fallback to ID if name not available
            breadcrumbs.push({ name: categoryName, url: `/categories/${categoryId}`, position: 3 });
        } else if (allBooksMatch) {
            breadcrumbs.push({ name: 'All Books', url: '/books', position: 2 });
        } else if (this.currentBook) {
            // Use origin category if user came from a category page
            if (this.originCategory) {
                breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
                breadcrumbs.push({
                    name: this.originCategory.name,
                    url: `/categories/${this.originCategory.id}`,
                    position: 3
                });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 4
                });
            }
            // Use Discover if user came from Discover page
            else if (this.originDiscover) {
                breadcrumbs.push({ name: 'Discover', url: '/discover', position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }
            // Use Author if user came from Author page
            else if (this.originAuthor) {
                breadcrumbs.push({ name: this.originAuthor.name, url: `/authors/${this.originAuthor.slug}`, position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }
            // Otherwise use All Books
            else {
                breadcrumbs.push({ name: 'All Books', url: '/books', position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }

            if (summaryMatch) {
                breadcrumbs.push({ name: 'Summary', url: path, position: breadcrumbs.length + 1 });
            } else if (chapterMatch) {
                const chapterNum = parseInt(chapterMatch[2]);
                // Try to find the chapter in the loaded chapters to get the title
                const chapter = this.chapters.find(c => c.chapter_number === chapterNum);
                const chapterTitle = chapter?.chapter_title || null;
                const chapterName = chapterTitle
                    ? `${chapterNum}. ${chapterTitle}`
                    : `Chapter ${chapterNum}`;
                breadcrumbs.push({
                    name: chapterName,
                    url: path,
                    position: breadcrumbs.length + 1
                });
            }
        }

        return breadcrumbs;
    }

    /**
     * Hide all breadcrumb navigations
     */
    hideAllBreadcrumbs() {
        const sections = ['book', 'medium', 'chapter', 'category', 'all-categories', 'blog', 'blog-post', 'author'];
        sections.forEach(section => {
            const breadcrumbNav = document.getElementById(`breadcrumb-nav-${section}`);
            if (breadcrumbNav) {
                breadcrumbNav.classList.add('hidden');
            }
        });
    }

    /**
     * Render breadcrumbs in the navigation
     * @param {Array} breadcrumbs - Array of breadcrumb objects
     * @param {string} section - Section identifier (book, medium, chapter, category, all-categories)
     */
    renderBreadcrumbs(breadcrumbs, section = 'book') {
        const breadcrumbNav = document.getElementById(`breadcrumb-nav-${section}`);
        const breadcrumbList = document.getElementById(`breadcrumb-list-${section}`);

        if (!breadcrumbNav || !breadcrumbList) return;

        // Hide breadcrumbs on home page
        if (breadcrumbs.length <= 1) {
            breadcrumbNav.classList.add('hidden');
            return;
        }

        // Show breadcrumbs
        breadcrumbNav.classList.remove('hidden');

        // Build breadcrumb HTML
        const breadcrumbHTML = breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;

            if (isLast) {
                // Last item - current page (no link)
                return `
                    <li class="breadcrumb-item">
                        <span class="breadcrumb-current">${this.escapeHtml(crumb.name)}</span>
                    </li>
                `;
            } else {
                // Intermediate items - with links
                return `
                    <li class="breadcrumb-item">
                        <a href="${crumb.url}" class="breadcrumb-link">${this.escapeHtml(crumb.name)}</a>
                        <span class="breadcrumb-separator">›</span>
                    </li>
                `;
            }
        }).join('');

        breadcrumbList.innerHTML = breadcrumbHTML;
    }

    /**
     * Update breadcrumbs based on current page
     * @param {string} section - Section identifier (book, medium, chapter, category, all-categories)
     */
    updateBreadcrumbs(section = 'book') {
        // Hide all breadcrumbs first to prevent persistence
        this.hideAllBreadcrumbs();

        // Build and render breadcrumbs for the active section
        const breadcrumbs = this.buildBreadcrumbs();
        this.renderBreadcrumbs(breadcrumbs, section);
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
                    const response = await fetch(`/api/admin/chapters/${this.currentBook.id}/${this.currentChapter}`, {
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
}

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
            const response = await fetch('/api/books');
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
                    <img src="/static/covers/${book.cover_image}"
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
                window.history.pushState(null, '', `/books/${slug}`);
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
            window.history.pushState(null, '', `/${route}`);
            window.summraApp.handleRoute();
        });
    });
});
