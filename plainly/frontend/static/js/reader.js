// Chapter-reading mixin for SummraApp — markdown/text rendering, the
// side-by-side original/plain-English view, chapter view-mode switching, and
// the main showChapterDetail page controller. Extracted from app.js (Phase
// 4b continuation); merged onto SummraApp.prototype via Object.assign in
// app.js, so every method still reads/writes `this.*` exactly as before.
// The continuous reader itself is the shared platform's continuousReaderMixin
// (shared/static/js/continuous_reader.js); classifyUnit() below is Plainly's
// hook that turns one unit's text into a block for the shared block renderer
// (shared/static/js/blocks.js).
export const readerMixin = {
    renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        return this.escapeHtml(text).replace(/\n/g, '<br>');
    },

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
                // Convert *text* to <em>text</em> for italic emphasis (markdown syntax)
                escaped = escaped.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
                return `<p>${escaped}</p>`;
            })
            .join('');
    },

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
                <div class="side-by-side-header">Plain English</div>
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
                escaped = escaped.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
                originalFormatted = escaped;
            } else {
                originalFormatted = '&nbsp;';
            }

            // Format modern paragraph
            let modernFormatted = '';
            if (modernPara) {
                let escaped = this.escapeHtml(modernPara.trim());
                escaped = escaped.replace(/\b_([^_]+?)_\b/g, '<em>$1</em>');
                escaped = escaped.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
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
    },

    showChapterDetailPage(chapterNum) {
        this.updateURL(this.currentBook, chapterNum);
        this.showChapterDetail(this.currentBook, chapterNum);
    },

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
            ttsBtn.onclick = () => this.onListenClick('medium', this.mediumSummaryContent);
            this.renderListenButton();
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
        this.updatePageTitle(`Summary of ${book.title} by ${book.author} | Plainly`);
    },

    /**
     * Get the current active view mode
     * @returns {string} - 'summary' | 'original' | 'modern' | 'side-by-side'
     */
    getCurrentViewMode() {
        const activeBtn = document.querySelector('.unified-view-btn.active');
        if (activeBtn) {
            return activeBtn.dataset.mode;
        }
        // Default to original if no active button found
        return 'original';
    },

    /**
     * Apply chapter view mode and return the container to paginate (DRY helper)
     * @param {string} viewMode - 'summary', 'original', 'modern', or 'side-by-side'
     * @returns {HTMLElement} - The container element to paginate
     */
    applyChapterViewMode(viewMode) {
        const summaryContentEl = document.getElementById('chapter-summary-content');
        const fulltextSectionEl = document.getElementById('chapter-fulltext-section');
        const fullTextEl = document.getElementById('chapter-fulltext');
        const modernEnglishEl = document.getElementById('chapter-modern-english');
        const sideBySideEl = document.getElementById('chapter-side-by-side');

        // Hide all containers first
        summaryContentEl.classList.add('hidden');
        fullTextEl.classList.add('hidden');
        modernEnglishEl.classList.add('hidden');
        sideBySideEl.classList.add('hidden');

        // Show the appropriate section and container based on mode
        if (viewMode === 'summary') {
            summaryContentEl.classList.remove('hidden');
            fulltextSectionEl.classList.add('hidden');
            return document.getElementById('chapter-summary-text');
        } else if (viewMode === 'modern') {
            fulltextSectionEl.classList.remove('hidden');
            modernEnglishEl.classList.remove('hidden');
            return modernEnglishEl;
        } else if (viewMode === 'side-by-side') {
            fulltextSectionEl.classList.remove('hidden');
            sideBySideEl.classList.remove('hidden');
            return sideBySideEl;
        } else {
            // original
            fulltextSectionEl.classList.remove('hidden');
            fullTextEl.classList.remove('hidden');
            return fullTextEl;
        }
    },

    async showChapterDetail(book, chapterNum, restoreScroll = false) {
        this.currentBook = book;
        this.currentChapter = chapterNum;

        // Clear all pagination data when navigating to a new chapter
        this.clearAllPaginationData();

        // Save current scroll position before navigating
        this.saveScrollPosition();

        // Set current page key
        const pageKey = `chapter_${book.id}_${chapterNum}`;
        this.setCurrentPage(pageKey);

        // Show only chapter detail section
        this.showOnlySections('chapter-detail-section');

        // Hide chapter section content to prevent flash before pagination completes
        const chapterSection = document.getElementById('chapter-detail-section');
        if (chapterSection) {
            chapterSection.style.visibility = 'hidden';
        }

        // Fetch individual chapter data on demand (optimized - only fetches one chapter)
        let chapter = this.chapters.find(c => c.chapter_number === chapterNum);

        // Declared here (not inside the block below) so the "chapter not found"
        // guard after that block can also reach it.
        const chapterFulltext = document.getElementById('chapter-fulltext');

        // If chapter doesn't have full details (summary/text), fetch them
        if (!chapter || !chapter.summary) {
            // Show loading state only when fetching new data
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

        // Update sticky header
        const chapterTitle = chapter.chapter_title || `Chapter ${chapterNum}`;

        // Prepare illustration data for pagination (will be used as page 0 if available)
        // Hide the standalone illustration container - it will be shown in pagination instead
        const illustrationContainer = document.getElementById('chapter-illustration-container');
        if (illustrationContainer) {
            illustrationContainer.classList.add('hidden');
        }

        // Store illustration data as instance property so it's accessible everywhere
        this.currentIllustrationData = null;
        if (chapter.illustration_url && chapter.illustration_url.trim() !== '') {
            // Store illustration data to be used in pagination
            this.currentIllustrationData = {
                ...this.illustrationSources(chapter.illustration_url),
                alt: `Illustration for ${chapterTitle}`
            };
        }

        // Wait for DOM to be ready before accessing elements
        setTimeout(() => {
            // Setup sticky back button
            const stickyBackBtn = document.getElementById('sticky-back-btn');
            if (stickyBackBtn) {
                stickyBackBtn.onclick = () => {
                    // Navigate back to book page with proper URL update
                    window.history.pushState({
                        type: 'book',
                        bookId: book.id,
                        bookSlug: book.slug
                    }, '', withBasePath(`/books/${book.slug}`));
                    this.handleRoute();
                };
            }

            // Update chapter title in sticky header
            const stickyTitleDisplay = document.getElementById('sticky-chapter-title-display');
            if (stickyTitleDisplay) {
                stickyTitleDisplay.textContent = `${chapterNum}. ${chapterTitle}`;
            }

            // Setup unified view toggle (Summary/Original/Modern/Side×Side)
            const unifiedToggle = document.getElementById('unified-view-toggle');
            const summaryBtn = unifiedToggle?.querySelector('[data-mode="summary"]');
            const originalBtn = unifiedToggle?.querySelector('[data-mode="original"]');
            const modernBtn = unifiedToggle?.querySelector('[data-mode="modern"]');
            const sideBySideBtn = unifiedToggle?.querySelector('[data-mode="side-by-side"]');

            // Determine which buttons to show
            const hasSummary = !!chapter.summary;
            const hasModern = !!chapter.modern_english_text;

            // Show/hide buttons based on available content
            if (summaryBtn) {
                summaryBtn.classList.toggle('hidden', !hasSummary);
            }
            if (modernBtn) {
                modernBtn.classList.toggle('hidden', !hasModern);
            }
            if (sideBySideBtn) {
                sideBySideBtn.classList.toggle('hidden', !hasModern);
            }

            // Calculate total visible buttons
            const visibleButtons = [hasSummary, true, hasModern, hasModern].filter(Boolean).length;

            // Hide entire toggle if only Original is available
            if (unifiedToggle) {
                if (visibleButtons === 1) {
                    unifiedToggle.classList.add('hidden');
                } else {
                    unifiedToggle.classList.remove('hidden');
                }
            }

            // Wire up unified toggle click handlers (must be inside setTimeout to ensure buttons are ready)
            // Remove old listeners by cloning and replacing nodes to prevent stacking
            const unifiedViewBtns = document.querySelectorAll('.unified-view-btn');
            unifiedViewBtns.forEach(btn => {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
            });

            // Now add fresh event listeners to the new buttons
            const freshUnifiedViewBtns = document.querySelectorAll('.unified-view-btn');
            freshUnifiedViewBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const mode = btn.dataset.mode;
                    const summaryContentEl = document.getElementById('chapter-summary-content');
                    const fulltextSectionEl = document.getElementById('chapter-fulltext-section');
                    const fullTextEl = document.getElementById('chapter-fulltext');
                    const modernEnglishEl = document.getElementById('chapter-modern-english');
                    const sideBySideEl = document.getElementById('chapter-side-by-side');

                    // Check if trying to view side-by-side on narrow screen
                    const isScreenTooNarrow = () => window.innerWidth < 1024;
                    if (mode === 'side-by-side' && isScreenTooNarrow()) {
                        alert('Side-by-side view requires a wider screen. Please expand your browser window or use a larger device.');
                        return;
                    }

                    // Update active button - only one can be active
                    freshUnifiedViewBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Save view mode preference
                    this.saveReadingPreference('chapterViewMode', mode);

                    // Reinitialize pagination for the new view mode
                    setTimeout(() => {
                        this.clearPagination();

                        // Set flag to reset to page 1 when switching tabs (don't load saved position)
                        if (this.pagination) {
                            this.pagination.shouldResetToPage1 = true;
                        }

                        // Apply view mode and get container to paginate (DRY - uses shared helper)
                        const containerToPaginate = this.applyChapterViewMode(mode);
                        this.initializePagination(containerToPaginate, mode, this.currentIllustrationData);
                    }, 50);
                });
            });
        }, 50);

        // Load full text
        const fullTextEl = document.getElementById('chapter-fulltext');
        if (chapter.chapter_text) {
            fullTextEl.innerHTML = this.formatChapterText(chapter.chapter_text);
        } else {
            fullTextEl.innerHTML = '<p class="error">Full text not available for this chapter</p>';
        }

        // Populate chapter summary if available
        const chapterSummaryContent = document.getElementById('chapter-summary-content');
        const chapterSummaryTextEl = document.getElementById('chapter-summary-text');
        if (chapterSummaryTextEl) {
            if (chapter.summary) {
                chapterSummaryTextEl.innerHTML = this.renderMarkdown(chapter.summary);
            } else {
                // Clear loading spinner if no summary available
                chapterSummaryTextEl.innerHTML = '<p style="color: #999; text-align: center; padding: 2rem;">No summary available for this chapter</p>';
            }
        }

        // Handle unified view toggle for all views
        const modernEnglishEl = document.getElementById('chapter-modern-english');
        const sideBySideEl = document.getElementById('chapter-side-by-side');
        const summaryContentEl = document.getElementById('chapter-summary-content');
        const fulltextSectionEl = document.getElementById('chapter-fulltext-section');

        // Show TTS button in sticky header
        const stickyTTSBtn = document.getElementById('sticky-fulltext-tts');
        if (stickyTTSBtn) {
            stickyTTSBtn.classList.remove('hidden');
        }

        // Populate modern English container if available
        if (chapter.modern_english_text) {
            modernEnglishEl.innerHTML = this.formatChapterText(chapter.modern_english_text);

            // Populate side-by-side container with aligned paragraph rows
            const sideBySideFormatted = this.formatSideBySideText(
                chapter.chapter_text,
                chapter.modern_english_text
            );
            sideBySideEl.innerHTML = sideBySideFormatted;

            // Function to check if screen is too narrow for side-by-side view
            const isScreenTooNarrow = () => window.innerWidth < 1024;

            // Resolve the initial view mode (honors valid saved preference,
            // otherwise prefers Plain English when available, else Original).
            const viewModeToApply = window.resolveInitialChapterViewMode({
                savedMode: localStorage.getItem('reading_chapterViewMode'),
                hasModern: !!chapter.modern_english_text,
                hasSummary: !!chapter.summary,
                isScreenTooNarrow: isScreenTooNarrow(),
            });

            // Setup unified view toggle event listeners
            const unifiedViewBtns = document.querySelectorAll('.unified-view-btn');

            // Set active button based on applied view mode
            unifiedViewBtns.forEach(btn => {
                if (btn.dataset.mode === viewModeToApply) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Function to update side-by-side button visibility based on screen width
            const updateSideBySideButtonVisibility = () => {
                const sideBySideBtn = document.querySelector('.unified-view-btn[data-mode="side-by-side"]');

                if (sideBySideBtn) {
                    if (isScreenTooNarrow()) {
                        sideBySideBtn.style.display = 'none';

                        // If currently viewing side-by-side, switch to original view
                        if (!sideBySideEl.classList.contains('hidden')) {
                            console.log('[Resize] Screen too narrow, switching from side-by-side to original');

                            // Query for current buttons (don't use stale reference)
                            const allBtns = document.querySelectorAll('.unified-view-btn');
                            const originalBtn = document.querySelector('.unified-view-btn[data-mode="original"]');
                            if (originalBtn) {
                                allBtns.forEach(b => b.classList.remove('active'));
                                originalBtn.classList.add('active');
                                summaryContentEl.classList.add('hidden');
                                fulltextSectionEl.classList.remove('hidden');
                                fullTextEl.classList.remove('hidden');
                                modernEnglishEl.classList.add('hidden');
                                sideBySideEl.classList.add('hidden');

                                // Reinitialize pagination for original view
                                this.clearPagination();
                                const containerToPaginate = this.applyChapterViewMode('original');
                                this.initializePagination(containerToPaginate, 'original', this.currentIllustrationData);
                            }
                        }
                    } else {
                        // Just show the button when screen is wide enough
                        // Stay on current view (don't auto-switch back to side-by-side)
                        sideBySideBtn.style.display = '';
                    }
                }
            };

            // Initial check
            updateSideBySideButtonVisibility();

            // Update on resize with debouncing to prevent excessive calls
            let resizeTimeout;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimeout);
                resizeTimeout = setTimeout(updateSideBySideButtonVisibility, 150);
            });

        } else {
            // No modern English available
            fullTextEl.classList.remove('hidden');
            modernEnglishEl.classList.add('hidden');
            sideBySideEl.classList.add('hidden');
        }

        // Setup fulltext TTS button in sticky header - only show if audio is available
        const stickyFulltextTtsBtn = document.getElementById('sticky-fulltext-tts');
        if (stickyFulltextTtsBtn) {
            if (chapter.chapter_text && chapter.has_audio) {
                stickyFulltextTtsBtn.classList.remove('hidden');
                stickyFulltextTtsBtn.onclick = () => {
                    this.generateChapterTTS(chapterNum, chapter.chapter_text, stickyFulltextTtsBtn, 'fulltext');
                };
            } else {
                stickyFulltextTtsBtn.classList.add('hidden');
            }
        }

        // Update sticky header title with chapter and book name
        this.updateStickyHeaderTitle(book.title, chapterNum, chapterTitle);

        // Initialize pagination for the active view mode
        setTimeout(() => {
            // Clear any existing pagination
            this.clearPagination();

            // Resolve the initial view mode (same helper as the toggle setup above).
            const savedViewMode = window.resolveInitialChapterViewMode({
                savedMode: localStorage.getItem('reading_chapterViewMode'),
                hasModern: !!chapter.modern_english_text,
                hasSummary: !!chapter.summary,
                isScreenTooNarrow: window.innerWidth < 1024,
            });

            // Apply view mode and get container to paginate (DRY - uses same helper as view toggle)
            const containerToPaginate = this.applyChapterViewMode(savedViewMode);

            // Initialize pagination with illustration data
            console.log('Initializing pagination for container:', containerToPaginate, 'viewMode:', savedViewMode);
            if (containerToPaginate) {
                this.initializePagination(containerToPaginate, savedViewMode, this.currentIllustrationData);
            } else {
                console.error('Container to paginate is null!');
            }
        }, 100);

        // Restore scroll position or scroll to top
        if (restoreScroll) {
            this.restoreScrollPosition(pageKey);
        } else {
            window.scrollTo(0, 0);
        }

        // Update breadcrumbs
        this.updateBreadcrumbs('chapter');

        // Update page title
        this.updatePageTitle(`Full Text of ${chapterTitle} - ${book.title} | Plainly`);

        // Track chapter view for reading progress
        if (window.authModule && book.id) {
            await window.authModule.trackChapterView(book.id, chapterNum, 0);
        }
    },

    // Library progress cards (Library page and the home "Continue reading"
    // row). Listeners are scoped to `container` so two renders don't stack.
    renderLibraryCards(container, books, action) {
        container.innerHTML = books.map(book => {
            const cover = this.bookCoverHtml(book);
            const chapter = book.current_chapter?.chapter_title || (book.current_chapter ? `Chapter ${book.current_chapter.chapter_number}` : 'Beginning');
            const percentage = Math.max(0, Math.min(100, Number(book.furthest_percentage) || 0));
            // Reading-mode names on Library / Continue reading cards; the same
            // labels are in library_card() in _book_card.html.
            const mode = (this.readerMode(book.last_mode) || this.readerMode(this.readerConfig().default_modes[0])).library_label;
            const status = book.status === 'finished' ? 'Finished' : (percentage ? 'Continue reading' : 'Just started');
            const progressLabel = book.status === 'finished' || percentage ? `<span>${percentage}%</span>` : '';
            const unfinished = book.status === 'finished'
                ? `<button class="library-mark-unfinished" type="button" data-reader-unfinish="${book.id}">Mark unfinished</button>` : '';
            return `<article class="library-card" data-reader-book="${book.id}">
                <div class="library-card-cover-frame">${cover}</div>
                <div class="library-card-body">
                    <div class="library-card-meta"><span>${status}</span>${progressLabel}</div>
                    <h3>${this.escapeHtml(book.title)}</h3>
                    <p class="library-card-author">${this.escapeHtml(book.author)}</p>
                    <p class="library-card-location">${this.escapeHtml(chapter)} · ${mode}</p>
                    <div class="library-card-foot">
                        ${percentage ? `<div class="library-card-progress" aria-label="${percentage}% read"><span style="width: ${percentage}%"></span></div>` : ''}
                        <div class="library-card-actions"><button class="library-read-action" type="button" data-library-read="${book.id}">${action}<span aria-hidden="true">→</span></button>${unfinished}</div>
                    </div>
                </div>
            </article>`;
        }).join('');
        const findBook = async id => {
            await this.ensureBooksLoaded();
            return this.allBooks.find(item => item.id === Number(id));
        };
        container.querySelectorAll('[data-reader-book]').forEach(card => card.addEventListener('click', async () => {
            const book = await findBook(card.dataset.readerBook);
            if (book) this.selectBook(book);
        }));
        container.querySelectorAll('[data-library-read]').forEach(button => button.addEventListener('click', async event => {
            event.stopPropagation();
            const book = await findBook(button.dataset.libraryRead);
            if (!book) return;
            const readerPath = withBasePath(`/books/${book.slug || this.slugify(book.title)}/read`);
            if (window.location.pathname !== readerPath) {
                window.history.pushState({ type: 'reader', bookId: book.id }, '', readerPath);
            }
            await this.showContinuousReader(book);
        }));
        container.querySelectorAll('[data-reader-unfinish]').forEach(button => button.addEventListener('click', async event => {
            event.stopPropagation();
            await this.markReaderBookUnfinished(Number(button.dataset.readerUnfinish));
            await this.showLibrary();
        }));
    },

    async showLibrary() {
        this.continuousReader = { active: false };
        this.clearPagination();
        this.showOnlySections('library-section');
        // On a direct Library load, routing can begin before the async auth
        // probe has completed. Wait for the shared readiness promise before
        // choosing between the authenticated projection and device cache.
        await window.authModule?.initAuth?.();
        document.getElementById('library-nav-btn')?.classList.toggle('hidden', !window.authModule?.currentUser?.());
        const cards = await window.authModule?.getLibrary?.();
        const continueEl = document.getElementById('continue-reading-cards');
        const finishedEl = document.getElementById('finished-cards');
        const emptyEl = document.getElementById('library-empty');
        if (!cards || !continueEl || !finishedEl) return;
        this.renderLibraryCards(continueEl, cards.continue_reading, 'Continue');
        this.renderLibraryCards(finishedEl, cards.finished, 'Read again');
        emptyEl?.classList.toggle('hidden', cards.continue_reading.length + cards.finished.length > 0);
        document.getElementById('continue-reading-shelf')?.classList.toggle('hidden', !cards.continue_reading.length);
        document.getElementById('finished-shelf')?.classList.toggle('hidden', !cards.finished.length);
        this.updatePageTitle('Your Library | Plainly');
    },

    async markReaderBookUnfinished(bookId) {
        const state = await window.authModule?.getReaderState?.(bookId);
        const mode = state?.book?.last_mode;
        const modeState = state?.modes?.find(item => item.mode === mode);
        if (!mode || !modeState?.current_marker) return;
        await window.authModule?.queueReaderMutation?.({
            book_id: bookId, mode, current_marker: modeState.current_marker,
            event_cause: 'manual_unfinish', active_seconds_delta: 0, sequential_boundaries_delta: 0,
            base_revision: modeState.revision || 0,
        });
    },

    classifyUnit(text) {
        const value = (text || '').trim();
        // Verse passages (poetry books) keep their line breaks.
        if (value.includes('\n')) {
            return { type: 'verse', lines: value.split('\n') };
        }
        const heading = value.length <= 100 && (
            /^(?:Original Transcriber’s Notes|Original Transcriber's Notes)\s*:?$/i.test(value)
            || /^[A-Z][A-Z0-9\s’'.,:;!?()—–-]*$/.test(value)
        );
        if (heading) {
            return { type: 'h', text: value };
        }

        const numberedListItem = /^\s*\d+[.)]\s+/.test(value);
        const asteriskDivider = /^(?:\s*\*\s*){3,}$/.test(value);
        const bulletMatch = asteriskDivider ? null : value.match(/^\s*[*+-]\s{1,}/);
        const listItem = numberedListItem || !!bulletMatch;
        const content = bulletMatch
            ? `• ${value.slice(bulletMatch[0].length)}`
            : value;
        return { type: listItem ? 'li' : 'p', text: content };
    },

    async loadContinuousAbout() {
        const target = document.getElementById('reader-about-content');
        if (!target) return;
        try {
            const bookId = this.currentBook.id;
            const authorSlug = this.slugify(this.currentBook.author || '');
            const [bookResponse, overviewResponse, categoriesResponse, relatedResponse, authorResponse] = await Promise.all([
                fetch(`${this.apiBase}/books/${bookId}`),
                fetch(`${this.apiBase}/books/${bookId}/summary/comprehensive`),
                fetch(`${this.apiBase}/books/${bookId}/categories`),
                fetch(`${this.apiBase}/books/${bookId}/related`),
                authorSlug ? fetch(`${this.apiBase}/authors/${encodeURIComponent(authorSlug)}`) : Promise.resolve(null),
            ]);
            const [data, overview, categories, related, author] = await Promise.all([
                bookResponse.json(), overviewResponse.json().catch(() => ({})),
                categoriesResponse.json().catch(() => ({})), relatedResponse.json().catch(() => ({})),
                authorResponse ? authorResponse.json().catch(() => ({})) : Promise.resolve({}),
            ]);
            if (data.success) {
                const categoryList = (categories.categories || []).map(category => this.escapeHtml(category.name)).join(', ');
                const relatedList = (related.related || []).slice(0, 6).map(book =>
                    `<button type="button" class="reader-related-book" data-related-book="${book.id}">${this.escapeHtml(book.title)} <span>— ${this.escapeHtml(book.author || '')}</span></button>`
                ).join('');
                const overviewText = overview.summary?.content || overview.summary?.summary || '';
                target.innerHTML = `<h2>${this.escapeHtml(data.book.title)}</h2>
                    <p class="reader-about-author">${this.escapeHtml(data.book.author)}</p>
                    <p>${this.escapeHtml(data.book.about_text || 'About this book is coming soon.')}</p>
                    ${author?.author?.short_bio || author?.author?.long_bio ? `<h3>Author</h3><p>${this.escapeHtml(author.author.short_bio || author.author.long_bio)}</p>` : ''}
                    ${overviewText ? `<h3>Overview</h3><p>${this.escapeHtml(overviewText)}</p>` : ''}
                    ${categoryList ? `<h3>Categories</h3><p>${categoryList}</p>` : ''}
                    ${relatedList ? `<h3>Related books</h3><div class="reader-related-list">${relatedList}</div>` : ''}`;
                target.querySelectorAll('[data-related-book]').forEach(button => button.onclick = () => {
                    const next = this.allBooks.find(book => book.id === Number(button.dataset.relatedBook));
                    if (next) this.selectBook(next);
                });
            }
        } catch (_) { target.textContent = 'About this book is unavailable offline.'; }
    },
};
