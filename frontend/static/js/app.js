// Summra Frontend JavaScript - Redesigned

class SummraApp {
    constructor() {
        this.apiBase = '/api';
        this.currentBook = null;
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
        this.init();
    }

    init() {
        this.loadCategories();
        this.loadBooks();
        this.setupEventListeners();
        this.setupPersistentPlayer();
        this.setupRouting();
        this.configureMarked();
        this.setupReadingSettings();
        this.loadReadingPreferences();
    }

    setupRouting() {
        window.addEventListener('popstate', () => {
            this.handleRoute();
        });
        // Handle the initial route immediately (don't wait for load event)
        this.handleRoute();
    }

    async handleRoute() {
        const hash = window.location.hash;

        if (!hash || hash === '#' || hash === '#/') {
            this.showHomeSection();
            // Clear URL when intentionally navigating to home
            if (hash) {
                window.history.pushState(null, '', '/');
            }
            return;
        }

        // Parse routes:
        // #/book/{slug} - Book detail
        // #/book/{slug}/medium - Medium summary detail
        // #/book/{slug}/chapter/{num} - Chapter detail
        // #/category/{id} - Category detail
        // #/categories - All categories view
        // #/all-books - All books grid view
        const bookMatch = hash.match(/#\/book\/([^\/]+)$/);
        const mediumMatch = hash.match(/#\/book\/([^\/]+)\/medium$/);
        const chapterMatch = hash.match(/#\/book\/([^\/]+)\/chapter\/(\d+)$/);
        const categoryMatch = hash.match(/#\/category\/(\d+)$/);
        const categoriesMatch = hash === '#/categories';
        const allBooksMatch = hash === '#/all-books';

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
        let newHash = `#/book/${slug}`;

        if (page === 'medium') {
            newHash = `#/book/${slug}/medium`;
        } else if (typeof page === 'number') {
            newHash = `#/book/${slug}/chapter/${page}`;
        }

        if (window.location.hash !== newHash) {
            window.history.pushState(null, '', newHash);
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
        const backButton = document.getElementById('back-button');
        if (backButton) {
            backButton.addEventListener('click', () => {
                this.saveScrollPosition();
                window.location.hash = '#/';
            });
        }

        const mediumBackButton = document.getElementById('medium-back-button');
        if (mediumBackButton) {
            mediumBackButton.addEventListener('click', () => {
                if (this.currentBook) {
                    const slug = this.slugify(this.currentBook.title);
                    window.location.hash = `#/book/${slug}`;
                }
            });
        }

        const chapterBackButton = document.getElementById('chapter-back-button');
        if (chapterBackButton) {
            chapterBackButton.addEventListener('click', () => {
                if (this.currentBook) {
                    const slug = this.slugify(this.currentBook.title);
                    window.location.hash = `#/book/${slug}`;
                }
            });
        }

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

        // Get book counts for each category
        const categoriesWithCounts = await Promise.all(
            categories.map(async (category) => {
                try {
                    const response = await fetch(`${this.apiBase}/categories/${category.id}/books`);
                    const data = await response.json();
                    return {
                        ...category,
                        bookCount: data.success ? (data.books?.length || 0) : 0
                    };
                } catch (error) {
                    console.error(`Error loading books for category ${category.name}:`, error);
                    return { ...category, bookCount: 0 };
                }
            })
        );

        // Filter out categories with no books and sort by book count
        const categoriesWithBooks = categoriesWithCounts
            .filter(cat => cat.bookCount > 0)
            .sort((a, b) => b.bookCount - a.bookCount);

        // Show top 10 categories
        const topCategories = categoriesWithBooks.slice(0, 10);

        for (const category of topCategories) {
            try {
                const response = await fetch(`${this.apiBase}/categories/${category.id}/books`);
                const data = await response.json();

                if (data.success && data.books && data.books.length > 0) {
                    this.renderCategoryCarousel(category, data.books);
                }
            } catch (error) {
                console.error(`Error rendering category ${category.name}:`, error);
            }
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
            ? `<a href="#/category/${category.id}" class="view-all-link">View All →</a>`
            : `<a href="#/all-books" class="view-all-link">View All →</a>`;

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
                ? `<img src="${this.escapeHtml(book.cover_image_url)}" alt="${this.escapeHtml(book.title)} cover" class="carousel-book-cover" loading="lazy">`
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
        this.currentBook = book;
        this.currentView = 'book';

        // Save current scroll position
        this.saveScrollPosition();

        // Update book info
        const bookTitle = document.getElementById('book-title');
        const bookAuthor = document.getElementById('book-author');

        if (bookTitle) bookTitle.textContent = book.title;
        if (bookAuthor) bookAuthor.textContent = `by ${book.author}`;

        const bookCoverEl = document.getElementById('book-info-cover');
        if (bookCoverEl) {
            if (book.cover_image_url) {
                bookCoverEl.src = book.cover_image_url;
                bookCoverEl.alt = `${book.title} cover`;
                bookCoverEl.classList.remove('hidden');
            } else {
                bookCoverEl.classList.add('hidden');
            }
        }

        // Hide categories section when viewing a book
        const categoriesSection = document.getElementById('categories-section');
        if (categoriesSection) categoriesSection.classList.add('hidden');

        // Show book detail section
        this.showBookDetail(restoreScroll);

        // Load summaries and chapters
        await Promise.all([
            this.loadConciseSummary(),
            this.loadMediumSummary(),
            this.loadChapters()
        ]);

        // Update URL
        this.updateURL(book);
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
                    this.updateURL(this.currentBook, 'medium');
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
        this.currentSummaryType = null;
        this.currentChapter = null;
        this.mediumSummaryContent = null;

        this.restoreScrollPosition('home');
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
            // Fetch category and books if not cached
            try {
                const response = await fetch(`${this.apiBase}/categories/${categoryId}/books`);
                const data = await response.json();

                if (data.success) {
                    // Cache the data
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

        // Render cached or freshly fetched data
        if (categoryData) {
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

        // Setup back button - always go to home
        const backBtn = document.getElementById('category-back-button');
        backBtn.onclick = () => {
            this.saveScrollPosition();
            this.showHomeSection();
        };

        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
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

        // Setup back button - always go to home
        const backBtn = document.getElementById('all-categories-back-button');
        backBtn.onclick = () => {
            this.saveScrollPosition();
            this.showHomeSection();
        };

        if (restoreScroll) {
            this.restoreScrollPosition('all-categories');
        } else {
            window.scrollTo(0, 0);
        }
    }

    async displayAllCategories(categories) {
        const container = document.getElementById('all-categories-container');
        container.innerHTML = '';

        // Get book counts
        const categoriesWithCounts = await Promise.all(
            categories.map(async (category) => {
                try {
                    const response = await fetch(`${this.apiBase}/categories/${category.id}/books`);
                    const data = await response.json();
                    return {
                        ...category,
                        bookCount: data.success ? (data.books?.length || 0) : 0,
                        books: data.success ? data.books : []
                    };
                } catch (error) {
                    return { ...category, bookCount: 0, books: [] };
                }
            })
        );

        // Filter and sort
        const categoriesWithBooks = categoriesWithCounts
            .filter(cat => cat.bookCount > 0)
            .sort((a, b) => b.bookCount - a.bookCount);

        // Render each category carousel
        categoriesWithBooks.forEach(category => {
            this.renderCategoryCarousel(category, category.books, 'all-categories-container');
        });
    }

    async showAllBooksGrid(restoreScroll = false) {
        this.saveScrollPosition();
        this.currentView = 'all-books';
        this.setCurrentPage('all-books');

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

        // Setup back button - always go to home
        const backBtn = document.getElementById('category-back-button');
        backBtn.onclick = () => {
            this.saveScrollPosition();
            this.showHomeSection();
        };

        if (restoreScroll) {
            this.restoreScrollPosition('all-books');
        } else {
            window.scrollTo(0, 0);
        }
    }

    createBookCard(book) {
        const bookCard = document.createElement('div');
        bookCard.className = 'book-card';

        const coverImageHtml = book.cover_image_url
            ? `<img src="${this.escapeHtml(book.cover_image_url)}" alt="${this.escapeHtml(book.title)} cover" class="book-cover" loading="lazy">`
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
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SummraApp();
});
