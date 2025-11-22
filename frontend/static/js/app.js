// Summra Frontend JavaScript

class SummraApp {
    constructor() {
        this.apiBase = '/api';
        this.currentBook = null;
        this.currentSummaryType = null;
        this.allBooks = [];
        this.booksLoaded = false;
        this.currentPlayback = {
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null  // Track audio_id for cleanup
        };
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
        // Handle browser back/forward buttons
        window.addEventListener('popstate', () => {
            this.handleRoute();
        });

        // Handle initial route
        window.addEventListener('load', () => {
            this.handleRoute();
        });
    }

    async handleRoute() {
        const hash = window.location.hash;

        if (!hash || hash === '#' || hash === '#/') {
            // Home page - show books list
            if (this.currentBook !== null) {
                this.showBooksSection();
            }
            return;
        }

        // Parse route: #/book/{slug} or #/book/{slug}/{summary-type}
        const match = hash.match(/#\/book\/([^\/]+)(?:\/(.+))?/);
        if (!match) {
            return;
        }

        const bookSlug = match[1];
        const summaryType = match[2] || 'concise';

        // Wait for books to be loaded if not already
        if (!this.booksLoaded) {
            await this.waitForBooks();
        }

        // Find book by slug
        const book = this.allBooks.find(b => this.slugify(b.title) === bookSlug);
        if (book) {
            // Select book and summary type
            await this.selectBookFromRoute(book, summaryType);
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
            .replace(/[^\w\s-]/g, '') // Remove special chars
            .replace(/\s+/g, '-')      // Replace spaces with -
            .replace(/--+/g, '-')      // Replace multiple - with single -
            .trim();
    }

    updateURL(book, summaryType) {
        const slug = this.slugify(book.title);
        const newHash = summaryType === 'concise'
            ? `#/book/${slug}`
            : `#/book/${slug}/${summaryType}`;

        if (window.location.hash !== newHash) {
            window.history.pushState(null, '', newHash);
        }
    }

    configureMarked() {
        // Configure marked for better rendering
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

        // Play/Pause button
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

        // Stop button
        stopBtn.addEventListener('click', () => {
            this.stopPlayback();
        });

        // Progress bar click to seek
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            persistentAudio.currentTime = percent * persistentAudio.duration;
        });

        // Update progress and time
        persistentAudio.addEventListener('timeupdate', () => {
            if (persistentAudio.duration) {
                const percent = (persistentAudio.currentTime / persistentAudio.duration) * 100;
                progressFill.style.width = `${percent}%`;
                currentTimeSpan.textContent = this.formatTime(persistentAudio.currentTime);
                totalTimeSpan.textContent = this.formatTime(persistentAudio.duration);
            }
        });

        // Handle audio end
        persistentAudio.addEventListener('ended', () => {
            this.handleAudioEnded();
        });

        // Reset on load
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

        // Stop audio
        persistentAudio.pause();
        persistentAudio.currentTime = 0;
        persistentAudio.src = '';

        // Get audio_id for cleanup before resetting state
        const audioIdToCleanup = this.currentPlayback.audioId;

        // Reset state
        this.currentPlayback = {
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null  // Track audio_id for cleanup
        };

        // Hide player
        persistentPlayer.classList.add('hidden');
        playPauseBtn.textContent = '▶';

        // Call backend to stop TTS generation and cleanup chunks
        try {
            await fetch(`${this.apiBase}/tts/stop`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    audio_id: audioIdToCleanup  // Send audio_id for chunk cleanup
                })
            });
        } catch (error) {
            console.error('Error stopping TTS:', error);
        }
    }

    handleAudioEnded() {
        // Move to next chunk if available
        this.currentPlayback.currentChunk++;
        if (this.currentPlayback.currentChunk < this.currentPlayback.audioUrls.length) {
            this.playNextChunk();
        } else {
            // Playback complete
            const playPauseBtn = document.getElementById('player-play-pause');
            playPauseBtn.textContent = '▶';
            this.currentPlayback.isPlaying = false;
            console.log('Playback complete');
        }
    }

    async playNextChunk() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const chunkUrl = this.currentPlayback.audioUrls[this.currentPlayback.currentChunk];

        console.log(`Playing chunk ${this.currentPlayback.currentChunk + 1}/${this.currentPlayback.audioUrls.length}`);

        // Wait for chunk to be available if it's still being generated
        if (this.currentPlayback.currentChunk > 0) {
            const isReady = await this.waitForChunk(chunkUrl);
            if (!isReady) {
                console.error('Chunk not available');
                this.stopPlayback();
                return;
            }
        }

        // Load and play the chunk
        persistentAudio.src = chunkUrl;
        try {
            await persistentAudio.play();
            const playPauseBtn = document.getElementById('player-play-pause');
            playPauseBtn.textContent = '⏸';
            this.currentPlayback.isPlaying = true;
        } catch (error) {
            console.error('Error playing chunk:', error);
            this.stopPlayback();
        }
    }

    async waitForChunk(url, retries = 20) {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, { method: 'HEAD' });
                if (response.ok) {
                    console.log(`Chunk ready after ${i} retries`);
                    return true;
                }
            } catch (error) {
                // Chunk not ready yet
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        return false;
    }

    renderMarkdown(text) {
        // Render markdown to HTML safely
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        // Fallback: basic line break conversion
        return this.escapeHtml(text).replace(/\n/g, '<br>');
    }

    formatPlainText(text) {
        // Format plain text with double newlines into HTML paragraphs
        if (!text) return '';

        // Split on double newlines to get paragraphs
        const paragraphs = text.split(/\n\n+/);

        // Wrap each paragraph in <p> tags and escape HTML
        return paragraphs
            .filter(p => p.trim().length > 0)  // Remove empty paragraphs
            .map(p => `<p>${this.escapeHtml(p.trim())}</p>`)
            .join('');
    }

    formatChapterText(text) {
        // Format chapter text with single newlines into HTML paragraphs
        // Chapter text is normalized to have single newlines between paragraphs
        if (!text) return '';

        // Split on single newlines to get paragraphs
        const paragraphs = text.split(/\n/);

        // Wrap each paragraph in <p> tags and escape HTML
        return paragraphs
            .filter(p => p.trim().length > 0)  // Remove empty paragraphs
            .map(p => `<p>${this.escapeHtml(p.trim())}</p>`)
            .join('');
    }

    setupEventListeners() {
        // Back button
        document.getElementById('back-button').addEventListener('click', () => {
            this.showBooksSection();
        });

        // Summary option cards
        document.querySelectorAll('.option-card').forEach(card => {
            card.addEventListener('click', () => {
                const summaryType = card.dataset.type;
                this.selectSummaryType(summaryType);
            });
        });

        // TTS button
        document.getElementById('tts-button').addEventListener('click', () => {
            this.generateTTS();
        });
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
                        <p style="margin-top: 10px; font-size: 0.9rem;">
                            Run: <code>python scripts/generate_summaries.py path/to/book.txt</code>
                        </p>
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

            // Build cover image HTML if available
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

    selectBook(book) {
        this.currentBook = book;
        this.currentSummaryType = 'concise';

        // Update book info
        document.getElementById('book-title').textContent = book.title;
        document.getElementById('book-author').textContent = `by ${book.author}`;

        // Update book cover if available
        const bookCoverEl = document.getElementById('book-info-cover');
        if (book.cover_image_url) {
            bookCoverEl.src = book.cover_image_url;
            bookCoverEl.alt = `${book.title} cover`;
            bookCoverEl.classList.remove('hidden');
        } else {
            bookCoverEl.classList.add('hidden');
        }

        // Reset option cards and mark concise as active
        document.querySelectorAll('.option-card').forEach(card => {
            card.classList.remove('active');
        });
        document.querySelector('[data-type="concise"]').classList.add('active');

        // Show summary section
        document.getElementById('books-section').classList.add('hidden');
        document.getElementById('summary-section').classList.remove('hidden');

        // Load concise summary automatically
        this.loadSummary('concise');

        // Update URL
        this.updateURL(book, 'concise');
    }

    async selectBookFromRoute(book, summaryType) {
        // Similar to selectBook but also loads the summary
        this.currentBook = book;
        this.currentSummaryType = summaryType;

        // Update book info
        document.getElementById('book-title').textContent = book.title;
        document.getElementById('book-author').textContent = `by ${book.author}`;

        // Update book cover if available
        const bookCoverEl = document.getElementById('book-info-cover');
        if (book.cover_image_url) {
            bookCoverEl.src = book.cover_image_url;
            bookCoverEl.alt = `${book.title} cover`;
            bookCoverEl.classList.remove('hidden');
        } else {
            bookCoverEl.classList.add('hidden');
        }

        // Show summary section
        document.getElementById('books-section').classList.add('hidden');
        document.getElementById('summary-section').classList.remove('hidden');

        // Select the summary type
        document.querySelectorAll('.option-card').forEach(card => {
            card.classList.remove('active');
        });
        document.querySelector(`[data-type="${summaryType}"]`)?.classList.add('active');

        // Load the summary
        await this.loadSummary(summaryType);
    }

    selectSummaryType(summaryType) {
        // Update active state
        document.querySelectorAll('.option-card').forEach(card => {
            card.classList.remove('active');
        });
        document.querySelector(`[data-type="${summaryType}"]`).classList.add('active');

        this.currentSummaryType = summaryType;
        this.loadSummary(summaryType);

        // Update URL
        if (this.currentBook) {
            this.updateURL(this.currentBook, summaryType);
        }
    }

    async loadSummary(summaryType) {
        const summaryContent = document.getElementById('summary-content');
        summaryContent.classList.remove('hidden');
        summaryContent.innerHTML = '<div class="loading">Loading summary...</div>';

        try {
            const response = await fetch(
                `${this.apiBase}/books/${this.currentBook.id}/summary/${summaryType}`
            );
            const data = await response.json();

            if (data.success) {
                this.displaySummary(data, summaryType);
            } else {
                summaryContent.innerHTML = `
                    <div class="error">
                        <p>${data.error}</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading summary:', error);
            summaryContent.innerHTML = `
                <div class="error">
                    <p>Error loading summary. Please try again.</p>
                </div>
            `;
        }
    }

    displaySummary(data, summaryType) {
        const summaryContent = document.getElementById('summary-content');

        // Only show top-level TTS button for concise and medium
        const ttsButtonHtml = (summaryType !== 'comprehensive' && summaryType !== 'full') ? `
            <div class="summary-controls">
                <button class="tts-button" id="tts-button">
                    🔊 Listen to Summary
                </button>
                <div class="audio-player hidden" id="audio-player">
                    <audio controls id="audio-element"></audio>
                </div>
            </div>
        ` : '';

        summaryContent.innerHTML = `
            ${ttsButtonHtml}
            <div class="comprehensive-view hidden" id="comprehensive-view">
                <div id="chapters-container"></div>
            </div>
            <div class="full-view hidden" id="full-view">
                <div id="full-chapters-container"></div>
            </div>
            <div class="regular-summary hidden" id="regular-summary">
                <div class="summary-text" id="summary-text"></div>
            </div>
        `;

        // Re-attach TTS button listener only if it exists
        const ttsButton = document.getElementById('tts-button');
        if (ttsButton) {
            ttsButton.addEventListener('click', () => {
                this.generateTTS();
            });
        }

        if (summaryType === 'full') {
            // Display full-length view with vertical layout
            document.getElementById('full-view').classList.remove('hidden');
            const fullChaptersContainer = document.getElementById('full-chapters-container');

            // Display chapters with full text + summary (no overall analysis)
            if (data.chapters && data.chapters.length > 0) {
                data.chapters.forEach(chapter => {
                    const chapterItem = this.createFullChapterElement(chapter);
                    fullChaptersContainer.appendChild(chapterItem);
                });
            }
        } else if (summaryType === 'comprehensive') {
            // Display comprehensive view
            document.getElementById('comprehensive-view').classList.remove('hidden');
            const chaptersContainer = document.getElementById('chapters-container');

            // Add overall summary as first "chapter" (collapsed by default)
            const overallChapter = this.createChapterElement({
                chapter_number: 0,
                chapter_title: 'Overall Analysis',
                summary: data.summary.content
            });
            chaptersContainer.appendChild(overallChapter);

            // Display chapters
            if (data.chapters && data.chapters.length > 0) {
                data.chapters.forEach(chapter => {
                    const chapterItem = this.createChapterElement(chapter);
                    chaptersContainer.appendChild(chapterItem);
                });
            }
        } else {
            // Display regular summary
            document.getElementById('regular-summary').classList.remove('hidden');
            document.getElementById('summary-text').innerHTML = this.renderMarkdown(data.summary.content);
        }
    }

    createChapterElement(chapter) {
        const chapterItem = document.createElement('div');
        chapterItem.className = 'chapter-item';

        const chapterId = `chapter-${chapter.chapter_number}`;

        // Handle chapter 0 (Overall Analysis) specially
        const headerText = chapter.chapter_number === 0
            ? chapter.chapter_title  // "Overall Analysis"
            : `Chapter ${chapter.chapter_number}: ${this.escapeHtml(chapter.chapter_title || '')}`;

        chapterItem.innerHTML = `
            <div class="chapter-header">
                <h4>${headerText}</h4>
                <div class="chapter-actions">
                    <button class="chapter-listen-btn" data-chapter="${chapter.chapter_number}">
                        🔊 Listen
                    </button>
                    <button class="chapter-toggle" aria-label="Toggle chapter">▼</button>
                </div>
            </div>
            <div class="chapter-content" id="${chapterId}">
                <div class="chapter-summary">${this.renderMarkdown(chapter.summary)}</div>
            </div>
        `;

        // Toggle functionality
        const toggle = chapterItem.querySelector('.chapter-toggle');
        const content = chapterItem.querySelector('.chapter-content');

        // Only toggle when clicking the toggle button (not the whole header)
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isExpanded = content.classList.contains('expanded');
            if (isExpanded) {
                content.classList.remove('expanded');
                toggle.classList.remove('expanded');
            } else {
                content.classList.add('expanded');
                toggle.classList.add('expanded');
            }
        });

        // Listen button functionality
        const listenBtn = chapterItem.querySelector('.chapter-listen-btn');
        const chapterSummaryEl = chapterItem.querySelector('.chapter-summary');
        listenBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            // Get text from DOM (already rendered, no markdown) instead of raw data
            const summaryText = chapterSummaryEl.textContent;
            this.generateChapterTTS(chapter.chapter_number, summaryText, listenBtn, 'summary');
        });

        return chapterItem;
    }

    createFullChapterElement(chapter) {
        const chapterItem = document.createElement('div');
        chapterItem.className = 'full-chapter-item';

        const chapterId = `full-chapter-${chapter.chapter_number}`;
        const headerText = `Chapter ${chapter.chapter_number}: ${this.escapeHtml(chapter.chapter_title || '')}`;

        // Vertical layout: Summary on top (collapsed), Full text below
        chapterItem.innerHTML = `
            <div class="chapter-header">
                <h4>${headerText}</h4>
                <div class="chapter-actions">
                    <button class="chapter-toggle" aria-label="Toggle chapter">▼</button>
                </div>
            </div>
            <div class="chapter-content" id="${chapterId}">
                <!-- Summary Section (collapsed by default) -->
                <div class="summary-section">
                    <div class="summary-section-header">
                        <h5>📝 Summary</h5>
                        <div class="summary-actions">
                            <button class="summary-listen-btn" data-chapter="${chapter.chapter_number}">
                                🔊 Listen
                            </button>
                            <button class="summary-toggle-btn" aria-label="Expand summary">▼</button>
                        </div>
                    </div>
                    <div class="summary-content collapsed">
                        ${this.renderMarkdown(chapter.summary)}
                    </div>
                </div>

                <!-- Full Text Section -->
                <div class="full-text-section">
                    <div class="full-text-section-header">
                        <h5>📖 Full Text</h5>
                        <button class="fulltext-listen-btn" data-chapter="${chapter.chapter_number}">
                            🔊 Listen
                        </button>
                    </div>
                    <div class="full-text-content">${this.formatChapterText(chapter.chapter_text || 'Full text not available.')}</div>
                </div>
            </div>
        `;

        // Toggle functionality for chapter expand/collapse
        const toggle = chapterItem.querySelector('.chapter-toggle');
        const content = chapterItem.querySelector('.chapter-content');

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isExpanded = content.classList.contains('expanded');
            if (isExpanded) {
                content.classList.remove('expanded');
                toggle.classList.remove('expanded');
            } else {
                content.classList.add('expanded');
                toggle.classList.add('expanded');
            }
        });

        // Summary toggle functionality
        const summaryToggleBtn = chapterItem.querySelector('.summary-toggle-btn');
        const summaryContent = chapterItem.querySelector('.summary-content');

        summaryToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isCollapsed = summaryContent.classList.contains('collapsed');
            if (isCollapsed) {
                summaryContent.classList.remove('collapsed');
                summaryToggleBtn.textContent = '▲';
                summaryToggleBtn.setAttribute('aria-label', 'Collapse summary');
            } else {
                summaryContent.classList.add('collapsed');
                summaryToggleBtn.textContent = '▼';
                summaryToggleBtn.setAttribute('aria-label', 'Expand summary');
            }
        });

        // Summary Listen button functionality
        const summaryListenBtn = chapterItem.querySelector('.summary-listen-btn');
        const chapterSummaryEl = chapterItem.querySelector('.summary-content');
        summaryListenBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const summaryText = chapterSummaryEl.textContent;
            this.generateChapterTTS(chapter.chapter_number, summaryText, summaryListenBtn, 'summary');
        });

        // Full Text Listen button functionality
        const fullTextListenBtn = chapterItem.querySelector('.fulltext-listen-btn');
        const fullTextEl = chapterItem.querySelector('.full-text-content');
        fullTextListenBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const fullText = fullTextEl.textContent;
            this.generateChapterTTS(chapter.chapter_number, fullText, fullTextListenBtn, 'fulltext');
        });

        return chapterItem;
    }

    truncateAtSentenceBoundary(text, maxChars = 5000) {
        /**
         * Truncate text at the last complete sentence before maxChars
         * Looks for sentence endings: . ! ? followed by space or end of text
         */
        if (text.length <= maxChars) {
            return text;
        }

        // Get substring up to maxChars
        let truncated = text.substring(0, maxChars);

        // Find the last sentence-ending punctuation followed by a space or end
        // Look for . ! ? followed by space (or end of string)
        const sentenceEndPattern = /[.!?][\s]/g;
        let lastMatch = null;
        let match;

        while ((match = sentenceEndPattern.exec(truncated)) !== null) {
            lastMatch = match;
        }

        if (lastMatch) {
            // Cut at the position after the punctuation and space
            truncated = truncated.substring(0, lastMatch.index + 2);
        } else {
            // No sentence ending found, try to at least break at a word boundary
            const lastSpace = truncated.lastIndexOf(' ');
            if (lastSpace > maxChars * 0.8) { // Only use word boundary if it's reasonably close
                truncated = truncated.substring(0, lastSpace);
            }
        }

        return truncated.trim();
    }

    cleanTextForTTS(text) {
        /**
         * Clean text for TTS by removing markdown formatting and special characters
         */
        let cleaned = text;

        // Replace curly quotes and apostrophes with straight ones
        cleaned = cleaned.replace(/[""]/g, '"');  // Curly double quotes
        cleaned = cleaned.replace(/['']/g, "'");  // Curly single quotes/apostrophes
        cleaned = cleaned.replace(/[«»]/g, '"');  // Guillemets
        cleaned = cleaned.replace(/…/g, '...');    // Ellipsis

        // Remove markdown headers (##, ###, etc.)
        cleaned = cleaned.replace(/^#{1,6}\s+/gm, '');

        // Remove bold/italic markers (**, __, *, _)
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');  // **bold**
        cleaned = cleaned.replace(/__([^_]+)__/g, '$1');      // __bold__
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');      // *italic*
        cleaned = cleaned.replace(/_([^_]+)_/g, '$1');        // _italic_

        // Remove links [text](url) -> text
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

        // Remove inline code `code`
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1');

        // Remove blockquotes (> )
        cleaned = cleaned.replace(/^>\s+/gm, '');

        // Remove horizontal rules (---, ***, ___)
        cleaned = cleaned.replace(/^[\-*_]{3,}\s*$/gm, '');

        // Remove list markers (-, *, 1., etc.)
        cleaned = cleaned.replace(/^[\s]*[-*+]\s+/gm, '');
        cleaned = cleaned.replace(/^[\s]*\d+\.\s+/gm, '');

        // Remove HTML tags (if any slipped through)
        cleaned = cleaned.replace(/<[^>]+>/g, '');

        // Remove special characters that don't make sense in speech
        cleaned = cleaned.replace(/[\[\]{}]/g, '');

        // Replace multiple punctuation with single
        cleaned = cleaned.replace(/!+/g, '!');    // Multiple exclamation
        cleaned = cleaned.replace(/\?+/g, '?');   // Multiple question marks
        cleaned = cleaned.replace(/\.{4,}/g, '...'); // More than 3 dots

        // Remove zero-width characters and other invisible Unicode
        cleaned = cleaned.replace(/[\u200B-\u200D\uFEFF]/g, '');

        // Normalize whitespace
        cleaned = cleaned.replace(/\s+/g, ' ');

        // Remove excessive newlines (keep sentences flowing)
        cleaned = cleaned.replace(/\n+/g, ' ');

        // Sanitize problematic punctuation combinations that cause TTS issues
        cleaned = cleaned.replace(/[?!]{2,}/g, '!');  // Replace ?!?! or similar with single !
        cleaned = cleaned.replace(/\.{4,}/g, '...');  // Replace many dots with ellipsis

        // Trim
        cleaned = cleaned.trim();

        // Ensure text ends with proper punctuation (models trained this way)
        if (cleaned && !cleaned.match(/[.!?]$/)) {
            cleaned = cleaned + '.';
        }

        return cleaned;
    }

    async generateTTS() {
        const ttsButton = document.getElementById('tts-button');

        // Get current summary text
        let summaryText = '';
        if (this.currentSummaryType === 'comprehensive') {
            // For comprehensive, get the overall summary text
            const overallSummaryEl = document.querySelector('#chapter-0 .chapter-summary');
            summaryText = overallSummaryEl ? overallSummaryEl.textContent : '';
        } else {
            summaryText = document.getElementById('summary-text').textContent;
        }

        if (!summaryText) {
            alert('No summary text available');
            return;
        }

        // Clean text for TTS (remove markdown and formatting)
        summaryText = this.cleanTextForTTS(summaryText);

        // Debug logging for TTS content
        console.log('=== TTS DEBUG ===');
        console.log('Summary Type:', this.currentSummaryType);
        console.log('Original text length:', summaryText.length);
        console.log('\nFull cleaned text:');
        console.log(summaryText);
        console.log('\n=================');

        // Disable button and show loading
        ttsButton.disabled = true;
        ttsButton.textContent = '🔄 Generating audio...';

        try {
            // Create unique ID for caching
            const audioId = `book_${this.currentBook.id}_${this.currentSummaryType}`;

            // Determine title for player
            const summaryTypeLabel = {
                'concise': 'Concise Summary',
                'medium': 'Medium Summary',
                'comprehensive': 'Overall Analysis'
            }[this.currentSummaryType];

            const textToSend = this.truncateAtSentenceBoundary(summaryText, 5000);
            console.log(`\nSending ${textToSend.length} characters to TTS API (truncated at sentence boundary)`);
            console.log('Final text to TTS API:');
            console.log(textToSend);
            console.log('=================\n');

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                if (data.cached) {
                    console.log('Using cached audio file');
                    ttsButton.textContent = '✓ Playing (cached)...';
                } else {
                    ttsButton.textContent = '✓ Playing...';
                }

                if (data.streaming && data.audio_urls) {
                    // Handle streaming audio chunks
                    this.startPersistentPlayback(data.audio_urls, this.currentBook.title, summaryTypeLabel, data.audio_id);
                } else {
                    // Handle single audio file (cached or short text)
                    this.startPersistentPlayback([data.audio_url], this.currentBook.title, summaryTypeLabel, data.audio_id);
                }

                // Re-enable button
                ttsButton.disabled = false;
                ttsButton.textContent = '🔊 Listen to Summary';
            } else {
                alert(`Error generating audio: ${data.error}`);
                ttsButton.textContent = '🔊 Listen to Summary';
                ttsButton.disabled = false;
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
            ttsButton.textContent = '🔊 Listen to Summary';
            ttsButton.disabled = false;
        }
    }

    async generateChapterTTS(chapterNumber, summaryText, buttonElement, contentType = 'summary') {
        /**
         * Generate and play TTS for a specific chapter using persistent player
         * @param contentType - 'summary' or 'fulltext' to distinguish cache keys
         */
        if (!summaryText) {
            alert('No summary text available');
            return;
        }

        // Show loading state on button
        const originalText = buttonElement.textContent;
        buttonElement.disabled = true;
        buttonElement.textContent = '⏳ Loading...';

        // Clean text for TTS
        const cleanedText = this.cleanTextForTTS(summaryText);

        // Debug logging for TTS content
        console.log('=== CHAPTER TTS DEBUG ===');
        console.log('Chapter Number:', chapterNumber);
        console.log('Content Type:', contentType);
        console.log('Original text length:', cleanedText.length);
        console.log('\nFull cleaned text:');
        console.log(cleanedText);
        console.log('\n=========================');

        // Create unique ID for this chapter - include content type to separate cache
        const audioId = `book_${this.currentBook.id}_chapter_${chapterNumber}_${contentType}`;

        // Set current playback info
        const chapterTitle = chapterNumber === 0
            ? 'Overall Analysis'
            : `Chapter ${chapterNumber}`;

        this.updatePlayerInfo(this.currentBook.title, chapterTitle);

        try {
            // For full chapter text, use much higher limit (20000 chars)
            const maxChars = contentType === 'fulltext' ? 20000 : 5000;
            const textToSend = this.truncateAtSentenceBoundary(cleanedText, maxChars);
            console.log(`\nSending ${textToSend.length} characters to TTS API for chapter ${chapterNumber} (${contentType}, truncated at sentence boundary)`);
            console.log('Final text to TTS API:');
            console.log(textToSend);
            console.log('=========================\n');

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                if (data.cached) {
                    console.log(`Using cached audio for chapter ${chapterNumber}`);
                }

                if (data.streaming && data.audio_urls) {
                    // Handle streaming audio chunks
                    this.startPersistentPlayback(data.audio_urls, this.currentBook.title, chapterTitle, data.audio_id);
                } else {
                    // Handle single audio file (cached or short text)
                    this.startPersistentPlayback([data.audio_url], this.currentBook.title, chapterTitle, data.audio_id);
                }
                // Reset button to normal state
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            } else {
                alert(`Error generating audio: ${data.error}`);
                // Reset button on error
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
            // Reset button on error
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

        // Update playback state
        this.currentPlayback = {
            isPlaying: true,
            currentChunk: 0,
            audioUrls: audioUrls,
            bookTitle: bookTitle,
            chapterTitle: chapterTitle,
            audioId: audioId  // Store audio_id for cleanup
        };

        // Update player info
        this.updatePlayerInfo(bookTitle, chapterTitle);

        // Show player
        persistentPlayer.classList.remove('hidden');

        // Start playing first chunk
        await this.playNextChunk();
    }

    async playAudioChunks(audioElement, audioUrls) {
        let currentChunkIndex = 0;
        const ttsButton = document.getElementById('tts-button');

        console.log(`Starting playback of ${audioUrls.length} chunks`);

        // Remove any existing ended listeners to prevent duplicate listeners
        const oldOnEnded = audioElement.onended;
        audioElement.onended = null;

        const waitForChunk = async (url, retries = 20) => {
            /**
             * Wait for a chunk to be available by checking if it loads
             * Returns true if chunk is ready, false if not available after retries
             */
            for (let i = 0; i < retries; i++) {
                try {
                    const response = await fetch(url, { method: 'HEAD' });
                    if (response.ok) {
                        console.log(`Chunk ${currentChunkIndex + 1} ready after ${i} retries`);
                        return true;
                    }
                } catch (error) {
                    // Chunk not ready yet
                }
                // Wait 500ms before retry
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            return false;
        };

        const playNextChunk = async () => {
            if (currentChunkIndex < audioUrls.length) {
                const chunkUrl = audioUrls[currentChunkIndex];
                const chunkNumber = currentChunkIndex + 1;

                console.log(`Playing chunk ${chunkNumber}/${audioUrls.length}: ${chunkUrl}`);

                // Update status
                ttsButton.textContent = `🔊 Playing ${chunkNumber}/${audioUrls.length}...`;

                // Wait for chunk to be available (for background-generated chunks)
                if (currentChunkIndex > 0) {
                    ttsButton.textContent = `⏳ Loading ${chunkNumber}/${audioUrls.length}...`;
                    const isReady = await waitForChunk(chunkUrl);
                    if (!isReady) {
                        console.error(`Chunk ${chunkNumber} not available after waiting`);
                        ttsButton.textContent = '❌ Audio generation failed';
                        ttsButton.disabled = false;
                        return;
                    }
                }

                // Set source and play the chunk
                audioElement.src = chunkUrl;
                currentChunkIndex++;

                try {
                    await audioElement.play();
                    console.log(`Chunk ${chunkNumber} playing`);
                } catch (error) {
                    console.error('Error playing chunk:', error);
                    ttsButton.textContent = '❌ Playback error';
                    ttsButton.disabled = false;
                }
            } else {
                // All chunks played
                console.log('All chunks completed');
                ttsButton.textContent = '✓ Playback complete';
                ttsButton.disabled = false;
                // Clean up listener
                audioElement.onended = null;
            }
        };

        // Set up single event handler using onended (not addEventListener to avoid duplicates)
        audioElement.onended = () => {
            console.log(`Chunk ended, moving to next (current index: ${currentChunkIndex})`);
            playNextChunk();
        };

        // Start playing the first chunk (guaranteed to be ready)
        await playNextChunk();
    }

    showBooksSection() {
        document.getElementById('summary-section').classList.add('hidden');
        document.getElementById('books-section').classList.remove('hidden');
        this.currentBook = null;
        this.currentSummaryType = null;

        // Update URL to home
        if (window.location.hash !== '' && window.location.hash !== '#/') {
            window.history.pushState(null, '', '/');
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
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SummraApp();
});
