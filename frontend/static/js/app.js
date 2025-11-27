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
        this.init();
    }

    init() {
        this.loadBooks();
        this.setupEventListeners();
        this.setupPersistentPlayer();
        this.setupRouting();
        this.configureMarked();
    }

    setupRouting() {
        window.addEventListener('popstate', () => {
            this.handleRoute();
        });
        window.addEventListener('load', () => {
            this.handleRoute();
        });
    }

    async handleRoute() {
        const hash = window.location.hash;

        if (!hash || hash === '#' || hash === '#/') {
            if (this.currentBook !== null) {
                this.showBooksSection();
            }
            return;
        }

        // Parse routes:
        // #/book/{slug} - Book detail
        // #/book/{slug}/medium - Medium summary detail
        // #/book/{slug}/chapter/{num} - Chapter detail
        const bookMatch = hash.match(/#\/book\/([^\/]+)$/);
        const mediumMatch = hash.match(/#\/book\/([^\/]+)\/medium$/);
        const chapterMatch = hash.match(/#\/book\/([^\/]+)\/chapter\/(\d+)$/);

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
                window.history.back();
            });
        }

        const mediumBackButton = document.getElementById('medium-back-button');
        if (mediumBackButton) {
            mediumBackButton.addEventListener('click', () => {
                this.saveScrollPosition();
                window.history.back();
            });
        }

        const chapterBackButton = document.getElementById('chapter-back-button');
        if (chapterBackButton) {
            chapterBackButton.addEventListener('click', () => {
                this.saveScrollPosition();
                window.history.back();
            });
        }
    }

    async loadBooks() {
        const booksGrid = document.getElementById('books-grid');
        booksGrid.innerHTML = '<div class="loading">Loading books...</div>';

        try {
            const response = await fetch(`${this.apiBase}/books`);
            const data = await response.json();

            if (data.success && data.books.length > 0) {
                this.allBooks = data.books;
                this.booksLoaded = true;
                this.displayBooks(data.books);
            } else {
                this.booksLoaded = true;
                booksGrid.innerHTML = `
                    <div class="error">
                        <p>No books found. Please add books using the summary generation script.</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading books:', error);
            this.booksLoaded = true;
            booksGrid.innerHTML = `
                <div class="error">
                    <p>Error loading books. Please make sure the backend server is running.</p>
                </div>
            `;
        }
    }

    displayBooks(books) {
        const booksGrid = document.getElementById('books-grid');
        booksGrid.innerHTML = '';

        books.forEach(book => {
            const bookCard = document.createElement('div');
            bookCard.className = 'book-card';

            const coverImageHtml = book.cover_image_url
                ? `<img src="${this.escapeHtml(book.cover_image_url)}" alt="${this.escapeHtml(book.title)} cover" class="book-cover">`
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
            booksGrid.appendChild(bookCard);
        });
    }

    async selectBook(book, restoreScroll = false) {
        this.currentBook = book;

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

        const booksSection = document.getElementById('books-section');
        const mediumDetailSection = document.getElementById('medium-detail-section');
        const chapterDetailSection = document.getElementById('chapter-detail-section');
        const summarySection = document.getElementById('summary-section');

        if (booksSection) booksSection.classList.add('hidden');
        if (mediumDetailSection) mediumDetailSection.classList.add('hidden');
        if (chapterDetailSection) chapterDetailSection.classList.add('hidden');
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

                // Setup TTS button
                const ttsBtn = document.getElementById('concise-tts-button');
                ttsBtn.onclick = () => this.generateTTS(data.summary.content, 'concise', ttsBtn);

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
            const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/comprehensive`);
            const data = await response.json();

            if (data.success && data.chapters && data.chapters.length > 0) {
                this.chapters = data.chapters;
                chaptersList.innerHTML = '';

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
        document.getElementById('books-section').classList.add('hidden');
        document.getElementById('summary-section').classList.add('hidden');
        document.getElementById('chapter-detail-section').classList.add('hidden');
        document.getElementById('medium-detail-section').classList.remove('hidden');

        // Update header
        document.getElementById('medium-detail-title').textContent = book.title;
        document.getElementById('medium-detail-subtitle').textContent = `by ${book.author}`;

        // Load or use cached medium summary
        if (!this.mediumSummaryContent) {
            try {
                const response = await fetch(`${this.apiBase}/books/${book.id}/summary/medium`);
                const data = await response.json();
                if (data.success && data.summary) {
                    this.mediumSummaryContent = data.summary.content;
                }
            } catch (error) {
                console.error('Error loading medium summary:', error);
            }
        }

        const mediumDetailText = document.getElementById('medium-detail-text');
        mediumDetailText.innerHTML = this.renderMarkdown(this.mediumSummaryContent || 'Summary not available');

        // Setup TTS button
        const ttsBtn = document.getElementById('medium-detail-tts-button');
        ttsBtn.onclick = () => this.generateTTS(this.mediumSummaryContent, 'medium', ttsBtn);

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }
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
        document.getElementById('books-section').classList.add('hidden');
        document.getElementById('summary-section').classList.add('hidden');
        document.getElementById('medium-detail-section').classList.add('hidden');
        document.getElementById('chapter-detail-section').classList.remove('hidden');

        // Load chapter data if not already loaded
        if (this.chapters.length === 0) {
            try {
                const response = await fetch(`${this.apiBase}/books/${book.id}/summary/comprehensive`);
                const data = await response.json();
                if (data.success && data.chapters) {
                    this.chapters = data.chapters;
                }
            } catch (error) {
                console.error('Error loading chapters:', error);
            }
        }

        const chapter = this.chapters.find(c => c.chapter_number === chapterNum);
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

            // Setup summary TTS button
            const summaryTtsBtn = document.getElementById('chapter-summary-tts-button');
            summaryTtsBtn.onclick = () => {
                this.generateChapterTTS(chapterNum, chapter.summary, summaryTtsBtn, 'summary');
            };
        }

        // Load full text
        const fullTextEl = document.getElementById('chapter-fulltext');
        if (chapter.chapter_text) {
            fullTextEl.innerHTML = this.formatChapterText(chapter.chapter_text);
        } else {
            fullTextEl.innerHTML = '<p class="error">Full text not available for this chapter</p>';
        }

        // Setup fulltext TTS button
        const fulltextTtsBtn = document.getElementById('chapter-fulltext-tts-button');
        if (chapter.chapter_text) {
            fulltextTtsBtn.onclick = () => {
                this.generateChapterTTS(chapterNum, chapter.chapter_text, fulltextTtsBtn, 'fulltext');
            };
        } else {
            fulltextTtsBtn.disabled = true;
        }

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }
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

    showBooksSection() {
        // Save current scroll position before navigating
        this.saveScrollPosition();

        // Set current page to home
        this.setCurrentPage('home');

        const summarySection = document.getElementById('summary-section');
        const mediumDetailSection = document.getElementById('medium-detail-section');
        const chapterDetailSection = document.getElementById('chapter-detail-section');
        const booksSection = document.getElementById('books-section');

        if (summarySection) summarySection.classList.add('hidden');
        if (mediumDetailSection) mediumDetailSection.classList.add('hidden');
        if (chapterDetailSection) chapterDetailSection.classList.add('hidden');
        if (booksSection) booksSection.classList.remove('hidden');

        this.currentBook = null;
        this.currentSummaryType = null;
        this.currentChapter = null;
        this.mediumSummaryContent = null;

        if (window.location.hash !== '' && window.location.hash !== '#/') {
            window.history.pushState(null, '', '/');
        }

        // Restore scroll position when going back to home
        this.restoreScrollPosition('home');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatNumber(num) {
        return num.toLocaleString();
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SummraApp();
});
