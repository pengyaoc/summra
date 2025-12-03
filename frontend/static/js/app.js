// Summra Frontend JavaScript - Redesigned

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
        this.init();
    }

    async init() {
        // Load books first, then categories (categories need books data for filtering)
        await this.loadBooks();
        await this.loadCategories();

        this.setupEventListeners();
        this.setupPersistentPlayer();
        this.setupRouting();
        this.configureMarked();
        this.setupReadingSettings();
        this.setupLightbox();
        this.loadReadingPreferences();
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
        const bookMatch = path.match(/^\/books\/([^\/]+)$/);
        const mediumMatch = path.match(/^\/books\/([^\/]+)\/summary$/);
        const chapterMatch = path.match(/^\/books\/([^\/]+)\/chapters\/(\d+)$/);
        const categoryMatch = path.match(/^\/categories\/(\d+)$/);
        const categoriesMatch = path === '/categories';
        const allBooksMatch = path === '/books';

        if (!this.booksLoaded) {
            await this.waitForBooks();
        }

        if (chapterMatch) {
            const bookSlug = chapterMatch[1];
            const chapterNum = parseInt(chapterMatch[2]);
            const book = this.allBooks.find(b => this.slugify(b.title) === bookSlug);
            if (book) {
                await this.showChapterDetail(book, chapterNum, true);
            }
        } else if (mediumMatch) {
            const bookSlug = mediumMatch[1];
            const book = this.allBooks.find(b => this.slugify(b.title) === bookSlug);
            if (book) {
                await this.showMediumDetail(book, true);
            }
        } else if (bookMatch) {
            const bookSlug = bookMatch[1];
            const book = this.allBooks.find(b => this.slugify(b.title) === bookSlug);
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
        const slug = this.slugify(book.title);
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
            .map(p => `<p>${this.escapeHtml(p.trim())}</p>`)
            .join('');
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

        // Add View All link (except for "All Books" carousel)
        const viewAllLink = category.id !== 'all'
            ? `<a href="/categories/${category.id}" class="view-all-link">View All →</a>`
            : `<a href="/books" class="view-all-link">View All →</a>`;

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

    async loadBooks() {
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

    async selectBook(book, restoreScroll = false) {
        // Track origin category for context-aware breadcrumbs BEFORE changing view
        // If we're currently viewing a category, store it as the origin
        if (this.currentView === 'category' && this.currentCategory) {
            this.originCategory = {
                id: this.currentCategory.id,
                name: this.currentCategory.name
            };
        }
        // If navigating from All Books or home, clear origin category
        else if (this.currentView === 'all-books' || this.currentView === 'home') {
            this.originCategory = null;
        }
        // Otherwise, keep the existing originCategory (e.g., when navigating within book pages)

        this.currentBook = book;
        this.currentView = 'book';

        // Save current scroll position
        this.saveScrollPosition();

        // Update book info
        const bookTitle = document.getElementById('book-title');
        const bookAuthor = document.getElementById('book-author');

        if (bookTitle) bookTitle.textContent = book.title;
        if (bookAuthor) bookAuthor.textContent = `by ${book.author}`;

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

        // Hide categories section when viewing a book
        const categoriesSection = document.getElementById('categories-section');
        if (categoriesSection) categoriesSection.classList.add('hidden');

        // Show book detail section
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

        const mediumDetailSection = document.getElementById('medium-detail-section');
        const chapterDetailSection = document.getElementById('chapter-detail-section');
        const summarySection = document.getElementById('summary-section');
        const categoryDetailSection = document.getElementById('category-detail-section');
        const allCategoriesSection = document.getElementById('all-categories-section');

        if (mediumDetailSection) mediumDetailSection.classList.add('hidden');
        if (chapterDetailSection) chapterDetailSection.classList.add('hidden');
        if (categoryDetailSection) categoryDetailSection.classList.add('hidden');
        if (allCategoriesSection) allCategoriesSection.classList.add('hidden');
        if (summarySection) summarySection.classList.remove('hidden');

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
        const authorCountryContainer = document.getElementById('author-country-container');
        const authorCountry = document.getElementById('author-country');
        const authorOtherBooksContainer = document.getElementById('author-other-books-container');
        const otherBooksList = document.getElementById('other-books-list');

        // Check if we have any data to display (backward compatibility)
        const hasAbout = book.about_text && book.about_text.trim();
        const hasRelevance = book.relevance_now && book.relevance_now.trim();
        const hasCountry = book.author_country && book.author_country.trim();
        const hasOtherBooks = book.author_other_books && book.author_other_books.trim();

        // Debug logging
        console.log('updateAboutSection called for:', book.title);
        console.log('Has metadata:', { hasAbout, hasRelevance, hasCountry, hasOtherBooks });

        // Only show section if we have at least some data
        if (!hasAbout && !hasRelevance && !hasCountry && !hasOtherBooks) {
            if (aboutSection) aboutSection.classList.add('hidden');
            return;
        }

        // Show section
        if (aboutSection) aboutSection.classList.remove('hidden');

        // Populate about text
        if (aboutText) {
            aboutText.textContent = hasAbout ? book.about_text : '';
            aboutText.parentElement.style.display = hasAbout ? 'block' : 'none';
        }

        // Populate relevance text
        if (relevanceText) {
            relevanceText.textContent = hasRelevance ? book.relevance_now : '';
            relevanceText.parentElement.style.display = hasRelevance ? 'block' : 'none';
        }

        // Populate author country
        if (authorCountry && hasCountry) {
            authorCountry.textContent = book.author_country;
            if (authorCountryContainer) authorCountryContainer.style.display = 'flex';
        } else {
            if (authorCountryContainer) authorCountryContainer.style.display = 'none';
        }

        // Populate other books by author
        if (hasOtherBooks) {
            const booksArray = book.author_other_books.split(',').map(b => b.trim()).filter(b => b);

            if (booksArray.length > 0) {
                otherBooksList.innerHTML = booksArray.map(bookTitle =>
                    `<div class="other-book-item">${this.escapeHtml(bookTitle)}</div>`
                ).join('');

                // Setup toggle for "More by Author"
                const toggle = document.getElementById('more-by-author-toggle');
                const label = document.getElementById('more-by-author-label');

                if (toggle && label) {
                    // Update label with author name
                    label.textContent = `More by ${book.author}`;

                    if (authorOtherBooksContainer) authorOtherBooksContainer.style.display = 'block';

                    // Remove old event listeners by cloning
                    const newToggle = toggle.cloneNode(true);
                    toggle.parentNode.replaceChild(newToggle, toggle);

                    newToggle.addEventListener('click', () => {
                        const isExpanded = !otherBooksList.classList.contains('hidden');
                        const arrow = newToggle.querySelector('.toggle-arrow');

                        if (isExpanded) {
                            otherBooksList.classList.add('hidden');
                            if (arrow) arrow.textContent = '▼';
                        } else {
                            otherBooksList.classList.remove('hidden');
                            if (arrow) arrow.textContent = '▲';
                        }
                    });
                }
            } else {
                if (authorOtherBooksContainer) authorOtherBooksContainer.style.display = 'none';
            }
        } else {
            if (authorOtherBooksContainer) authorOtherBooksContainer.style.display = 'none';
        }
    }

    async loadBookMetadata(bookId) {
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
        }
    }

    async loadConciseSummary() {
        const conciseSummaryText = document.getElementById('concise-summary-text');
        conciseSummaryText.innerHTML = '<div class="loading">Loading...</div>';

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/concise`);
            const data = await response.json();

            if (data.success && data.summary) {
                conciseSummaryText.innerHTML = this.renderMarkdown(data.summary.content);

                // Setup TTS button - only show if audio is available
                const ttsBtn = document.getElementById('concise-tts-button');
                if (data.has_audio) {
                    ttsBtn.classList.remove('hidden');
                    ttsBtn.onclick = () => this.generateTTS(data.summary.content, 'concise', ttsBtn);
                } else {
                    ttsBtn.classList.add('hidden');
                }

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
                        let isExpanded = false;
                        expandButton.onclick = () => {
                            isExpanded = !isExpanded;

                            if (isExpanded) {
                                // Expand
                                previewContainer.classList.add('expanded');
                                previewFade.classList.add('hidden');
                                expandButton.textContent = 'Show Less ↑';
                            } else {
                                // Collapse
                                previewContainer.classList.remove('expanded');
                                previewFade.classList.remove('hidden');
                                expandButton.textContent = 'Read Quick Summary →';

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
        mediumPreviewText.innerHTML = '<div class="loading">Loading...</div>';

        try {
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/medium`);
            const data = await response.json();

            if (data.success && data.summary) {
                this.mediumSummaryContent = data.summary.content;
                this.mediumSummaryHasAudio = data.has_audio || false; // Cache the audio flag
                // Show full content in preview (will be faded by CSS)
                mediumPreviewText.innerHTML = this.renderMarkdown(this.mediumSummaryContent);

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
        chaptersList.innerHTML = '<div class="loading">Loading chapters...</div>';

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

        // Hide other sections
        document.getElementById('summary-section').classList.add('hidden');
        document.getElementById('chapter-detail-section').classList.add('hidden');
        document.getElementById('medium-detail-section').classList.remove('hidden');

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

        // Hide other sections
        document.getElementById('summary-section').classList.add('hidden');
        document.getElementById('medium-detail-section').classList.add('hidden');
        document.getElementById('chapter-detail-section').classList.remove('hidden');

        // Fetch individual chapter data on demand (optimized - only fetches one chapter)
        let chapter = this.chapters.find(c => c.chapter_number === chapterNum);

        // If chapter doesn't have full details (summary/text), fetch them
        if (!chapter || !chapter.summary) {
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
            document.getElementById('chapter-detail-content').innerHTML = '<p class="error">Chapter not found</p>';
            return;
        }

        // Update header
        const chapterTitle = chapter.chapter_title || `Chapter ${chapterNum}`;
        document.getElementById('chapter-detail-title').textContent = `${chapterNum}. ${chapterTitle}`;
        document.getElementById('chapter-detail-subtitle').textContent = book.title;

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

        // Load summary (collapsed by default) - or hide if empty
        const summaryBox = document.getElementById('chapter-summary-box');
        const summaryText = document.getElementById('chapter-summary-text');

        if (!chapter.summary || chapter.summary.trim() === '') {
            // No summary available - hide entire summary section
            summaryBox.style.display = 'none';
        } else {
            // Summary available - show and populate
            summaryBox.style.display = '';
            summaryText.innerHTML = this.renderMarkdown(chapter.summary);

            // Setup toggle button
            const toggleBtn = document.getElementById('toggle-summary-btn');
            const summaryContent = document.getElementById('chapter-summary-content');
            let isSummaryExpanded = false;

            toggleBtn.onclick = () => {
                if (isSummaryExpanded) {
                    summaryContent.classList.add('hidden');
                    toggleBtn.textContent = '▼';
                    isSummaryExpanded = false;
                } else {
                    summaryContent.classList.remove('hidden');
                    toggleBtn.textContent = '▲';
                    isSummaryExpanded = true;
                }
            };

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
                this.startPersistentPlayback(audioUrls, this.currentBook.title, `${type} summary`, data.audio_id);
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
                this.startPersistentPlayback(audioUrls, this.currentBook.title, chapterTitle, data.audio_id);
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

            // Get book cover URL if available
            const coverUrl = this.currentBook && this.currentBook.cover_image_url
                ? window.location.origin + this.currentBook.cover_image_url
                : null;

            // Set metadata
            navigator.mediaSession.metadata = new MediaMetadata({
                title: chapterTitle,
                artist: bookTitle,
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

    async startPersistentPlayback(audioUrls, bookTitle, chapterTitle, audioId = null) {
        const persistentPlayer = document.getElementById('persistent-player');

        this.currentPlayback = {
            isPlaying: true,
            currentChunk: 0,
            audioUrls: audioUrls,
            bookTitle: bookTitle,
            chapterTitle: chapterTitle,
            audioId: audioId
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

    showHomeSection() {
        this.saveScrollPosition();
        this.setCurrentPage('home');
        this.currentView = 'home';

        // Hide all other sections
        const sections = ['summary-section', 'medium-detail-section', 'chapter-detail-section',
                         'category-detail-section', 'all-categories-section'];
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) section.classList.add('hidden');
        });

        // Show only categories section on home
        const categoriesSection = document.getElementById('categories-section');
        if (categoriesSection) categoriesSection.classList.remove('hidden');

        this.currentBook = null;
        this.currentCategory = null;
        this.currentSummaryType = null;
        this.currentChapter = null;
        this.mediumSummaryContent = null;
        this.originCategory = null;

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

        // Hide all sections except category detail
        const sections = ['categories-section', 'summary-section',
                         'medium-detail-section', 'chapter-detail-section', 'all-categories-section'];
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) section.classList.add('hidden');
        });

        const categoryDetailSection = document.getElementById('category-detail-section');
        categoryDetailSection.classList.remove('hidden');

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

            document.getElementById('category-detail-title').textContent = categoryData.category.name;
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

        // Hide all sections except all categories
        const sections = ['categories-section', 'summary-section',
                         'medium-detail-section', 'chapter-detail-section', 'category-detail-section'];
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) section.classList.add('hidden');
        });

        const allCategoriesSection = document.getElementById('all-categories-section');
        allCategoriesSection.classList.remove('hidden');

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

        // Clear category state since we're not viewing a category
        this.currentCategory = null;

        // Reuse category detail section for all books grid
        const sections = ['categories-section', 'summary-section',
                         'medium-detail-section', 'chapter-detail-section', 'all-categories-section'];
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) section.classList.add('hidden');
        });

        const categoryDetailSection = document.getElementById('category-detail-section');
        categoryDetailSection.classList.remove('hidden');

        document.getElementById('category-detail-title').textContent = 'All Books';
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
            const summaryText = chapterSection.querySelector('.chapter-summary-text');
            const summaryContentText = chapterSection.querySelector('#chapter-summary-content .summary-text');

            if (fulltext) fulltext.style.fontSize = `${size}px`;
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
        if (!nextChapterBtn) return;

        // Find the next chapter
        const nextChapter = this.chapters.find(ch => ch.chapter_number === currentChapterNum + 1);

        if (nextChapter) {
            nextChapterBtn.classList.remove('hidden');
            nextChapterBtn.onclick = () => {
                this.showChapterDetailPage(nextChapter.chapter_number);
            };
        } else {
            nextChapterBtn.classList.add('hidden');
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

        if (categoriesMatch) {
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
            // Use origin category if user came from a category page, otherwise use All Books
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
            } else {
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
        const sections = ['book', 'medium', 'chapter', 'category', 'all-categories'];
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
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SummraApp();
});
