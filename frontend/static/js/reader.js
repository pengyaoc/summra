// Chapter-reading mixin for SummraApp — markdown/text rendering, the
// side-by-side original/plain-English view, chapter view-mode switching, and
// the main showChapterDetail page controller. Extracted from app.js (Phase
// 4b continuation); merged onto SummraApp.prototype via Object.assign in
// app.js, so every method still reads/writes `this.*` exactly as before.
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

    async showResumeReadingButton() {
        if (!this.currentBook || !window.authModule) return;

        // Get reading progress
        const progress = await window.authModule.getReadingProgress(this.currentBook.id);

        // Find the book-detail-info section where we'll add the button
        const bookDetailInfo = document.querySelector('.book-detail-info');
        if (!bookDetailInfo) return;

        // Remove existing resume button if any
        const existingButton = document.getElementById('resume-reading-btn');
        if (existingButton) {
            existingButton.remove();
        }

        // Only show if there's progress
        if (progress && progress.chapter_number !== null) {
            // Get chapter title for better display
            const chapterName = progress.chapter_number === 0 ? 'Preface' : `Chapter ${progress.chapter_number}`;

            // Create resume reading button
            const resumeBtn = document.createElement('button');
            resumeBtn.id = 'resume-reading-btn';
            resumeBtn.className = 'resume-reading-btn';
            resumeBtn.innerHTML = `
                <span class="resume-icon">📖</span>
                <span class="resume-text">Continue Reading: ${chapterName}, Page ${progress.page_number + 1}</span>
            `;

            // Add click handler to navigate to last read chapter and page
            resumeBtn.addEventListener('click', async () => {
                await this.showChapterDetailPage(progress.chapter_number);

                // After chapter loads, navigate to the saved page
                if (progress.page_number && progress.page_number > 0) {
                    setTimeout(() => {
                        if (this.pagination && this.pagination.totalPages > progress.page_number) {
                            this.pagination.currentPage = progress.page_number;
                            this.displayCurrentPage();
                        }
                    }, 100);
                }
            });

            // Insert after the Save for Offline button in book-detail-info section
            bookDetailInfo.appendChild(resumeBtn);
        }
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
            let illustrationUrl = chapter.illustration_url;
            // Convert local path to URL if needed
            if (!illustrationUrl.startsWith('http')) {
                if (!illustrationUrl.startsWith('/static/')) {
                    illustrationUrl = `/static/${illustrationUrl}`;
                }
                illustrationUrl = withBasePath(illustrationUrl);
            }

            // Generate optimized image URLs (WebP and JPG)
            const baseUrl = illustrationUrl.replace(/\.(png|jpg|jpeg)$/i, '');
            const webpUrl = `${baseUrl}.webp`;
            const jpgUrl = `${baseUrl}.jpg`;

            // Store illustration data to be used in pagination
            this.currentIllustrationData = {
                baseUrl,
                webpUrl,
                jpgUrl,
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
        this.updatePageTitle(`Full Text of ${chapterTitle} - ${book.title} | Summra`);

        // Track chapter view for reading progress
        if (window.authModule && book.id) {
            await window.authModule.trackChapterView(book.id, chapterNum, 0);
        }
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
        const offline = document.getElementById('library-offline-note');
        if (!cards || !continueEl || !finishedEl) return;
        const render = (book, action) => {
            const rawCover = book.cover_image_url || '';
            const cover = rawCover && this.getImageHtml
                ? this.getImageHtml(rawCover, `${book.title} cover`, 'library-card-cover')
                : '<div class="library-cover-placeholder" aria-hidden="true">📖</div>';
            const chapter = book.current_chapter?.chapter_title || (book.current_chapter ? `Chapter ${book.current_chapter.chapter_number}` : 'Beginning');
            const percentage = Math.max(0, Math.min(100, Number(book.furthest_percentage) || 0));
            const mode = (book.last_mode || 'plain').replaceAll('_', ' ');
            const unfinished = book.status === 'finished'
                ? `<button class="library-mark-unfinished" type="button" data-reader-unfinish="${book.id}">Mark unfinished</button>` : '';
            return `<article class="library-card" data-reader-book="${book.id}">
                <div class="library-card-cover-frame">${cover}</div>
                <div class="library-card-body">
                    <div class="library-card-meta"><span>${book.status === 'finished' ? 'Finished' : 'Continue reading'}</span><span>${percentage}%</span></div>
                    <h3>${this.escapeHtml(book.title)}</h3>
                    <p class="library-card-author">${this.escapeHtml(book.author)}</p>
                    <p class="library-card-location">${this.escapeHtml(chapter)}</p>
                    <div class="library-card-progress" aria-label="${percentage}% read"><span style="width: ${percentage}%"></span></div>
                    <div class="library-card-actions"><button class="library-read-action" type="button" data-library-read="${book.id}">${action}<span aria-hidden="true">→</span></button>${unfinished}</div>
                    <p class="library-card-mode">${this.escapeHtml(mode)}</p>
                </div>
            </article>`;
        };
        continueEl.innerHTML = cards.continue_reading.map(book => render(book, 'Continue')).join('');
        finishedEl.innerHTML = cards.finished.map(book => render(book, 'Read again')).join('');
        emptyEl?.classList.toggle('hidden', cards.continue_reading.length + cards.finished.length > 0);
        document.getElementById('continue-reading-shelf')?.classList.toggle('hidden', !cards.continue_reading.length);
        document.getElementById('finished-shelf')?.classList.toggle('hidden', !cards.finished.length);
        offline?.classList.toggle('hidden', !cards.offline);
        document.querySelectorAll('[data-reader-book]').forEach(card => card.addEventListener('click', () => {
            const book = this.allBooks.find(item => item.id === Number(card.dataset.readerBook));
            if (book) this.selectBook(book);
        }));
        document.querySelectorAll('[data-library-read]').forEach(button => button.addEventListener('click', async event => {
            event.stopPropagation();
            const book = this.allBooks.find(item => item.id === Number(button.dataset.libraryRead));
            if (!book) return;
            const readerPath = withBasePath(`/books/${book.slug || this.slugify(book.title)}/read`);
            if (window.location.pathname !== readerPath) {
                window.history.pushState({ type: 'reader', bookId: book.id }, '', readerPath);
            }
            await this.showContinuousReader(book);
        }));
        document.querySelectorAll('[data-reader-unfinish]').forEach(button => button.addEventListener('click', async event => {
            event.stopPropagation();
            await this.markReaderBookUnfinished(Number(button.dataset.readerUnfinish));
            await this.showLibrary();
        }));
        this.updatePageTitle('Your Library | Summra');
    },

    async markReaderBookUnfinished(bookId) {
        const state = await window.authModule?.getReaderState?.(bookId);
        const mode = state?.book?.last_mode;
        const modeState = state?.modes?.find(item => item.mode === mode);
        if (!mode || !modeState?.current_marker) return;
        await window.authModule?.queueReaderMutation?.({
            book_id: bookId, mode, current_marker: modeState.current_marker,
            event_cause: 'manual_unfinish', active_seconds_delta: 0, sequential_boundaries_delta: 0,
            base_revision: modeState.revision || modeState.server_revision || 0,
        });
    },

    async showContinuousReader(book, options = {}) {
        if (this.continuousReader?.active && this.currentBook?.id !== book.id) {
            await this.saveContinuousReader('navigation');
        }
        this.currentBook = book;
        this.currentView = 'reader';
        this.clearAllPaginationData();
        this.showOnlySections('continuous-reader-section');
        const status = document.getElementById('reader-status');
        const content = document.getElementById('continuous-reader-content');
        status?.classList.remove('hidden');
        if (status) status.textContent = 'Opening book…';
        if (content) content.innerHTML = '';
        let manifest = null;
        try {
            const manifestResponse = await fetch(`${this.apiBase}/reader/books/${book.id}/manifest`);
            const manifestData = await manifestResponse.json();
            if (manifestResponse.ok && manifestData.success) {
                manifest = manifestData.manifest;
                window.authModule?.cacheReaderManifest?.(manifest).catch(() => {});
            }
        } catch (_) { /* use the durable segment cache below */ }
        manifest ||= await window.authModule?.getCachedReaderManifest?.(book.id);
        if (!manifest) {
            if (status) status.textContent = 'Unable to open this book. Retry.';
            return;
        }
        const state = await window.authModule?.getReaderState?.(book.id) || { book: null, modes: [] };
        const available = manifest.modes
            .filter(item => item.availability !== 'unavailable' && this.isContinuousReaderModeAvailable(item.mode))
            .map(item => item.mode);
        const requestedMode = options.mode;
        const savedMode = state.book?.last_mode;
        const mode = available.includes(requestedMode) ? requestedMode :
            (available.includes(savedMode) ? savedMode : (available.includes('plain') ? 'plain' : available.includes('original') ? 'original' : available[0]));
        if (!mode) {
            if (status) status.textContent = 'No readable content is available for this book.';
            return;
        }
        const modeState = state.modes?.find(item => item.mode === mode);
        let restoredMarker = modeState?.current_marker || null;
        let recoveryNotice = false;
        if (restoredMarker && restoredMarker.content_version !== manifest.content_version) {
            const recovered = await this.recoverContinuousMarker(restoredMarker);
            if (recovered) {
                restoredMarker = recovered;
                if (recovered.recovery_level === 'chapter_opening' || recovered.recovery_level === 'book_opening') {
                    recoveryNotice = true;
                    this.setContinuousReaderStatus('This book changed; your place was restored approximately.');
                }
            }
        }
        const chapterId = this.resolveReaderChapter(manifest, options.chapter, options.legacyChapterNumber);
        this.continuousReader = {
            active: true, restoring: true, manifest, mode, state, modeState,
            currentMarker: restoredMarker,
            recoveryNotice,
            furthestMarker: modeState?.furthest_marker || null,
            segmentIds: [], currentSegmentId: null, chapterId,
            lastDisplayedOrdinal: null, pageTurnAt: Date.now(), terminalTimer: null,
        };
        this.setupContinuousReaderChrome();
        this.setupContinuousReaderLifecycle();
        await this.loadContinuousReaderAt(this.continuousReader.currentMarker, chapterId);
        if (!this.continuousReader.recoveryNotice) status?.classList.add('hidden');
    },

    resolveReaderChapter(manifest, rawChapter, legacyNumber = false) {
        if (!rawChapter) return null;
        const chapter = manifest.structure.find(entry => entry.kind === 'chapter' &&
            (legacyNumber ? String(entry.chapter_number) === String(rawChapter) : String(entry.chapter_id) === String(rawChapter)));
        return chapter?.chapter_id || null;
    },

    isContinuousReaderModeAvailable(mode) {
        return mode !== 'side_by_side' || window.matchMedia('(min-width: 1024px)').matches;
    },

    async switchContinuousReaderMode(nextMode) {
        const reader = this.continuousReader;
        if (!reader?.active || nextMode === reader.mode || !this.isContinuousReaderModeAvailable(nextMode)) return;
        await this.saveContinuousReader('mode_exit');
        const previousMode = reader.mode;
        reader.mode = nextMode;
        reader.restoring = true;
        let destination = reader.state?.modes?.find(item => item.mode === reader.mode)?.current_marker || null;
        if (!destination && reader.currentMarker) {
            destination = await this.mapContinuousMarker(reader.currentMarker, previousMode, reader.mode);
        }
        await this.loadContinuousReaderAt(destination, reader.currentMarker?.chapter_id);
    },

    async enforceContinuousReaderViewport() {
        const reader = this.continuousReader;
        if (!reader?.active || reader.mode !== 'side_by_side' || this.isContinuousReaderModeAvailable('side_by_side')) {
            if (reader?.active) this.setupContinuousReaderChrome();
            return;
        }
        const fallback = reader.manifest.modes.find(item => item.mode === 'plain' && item.availability !== 'unavailable')?.mode || 'original';
        try {
            await this.switchContinuousReaderMode(fallback);
        } catch (_) {
            // The alignment anchor is also a plain-text anchor. Preserve it as
            // the best available location if the optional mapping request fails.
            reader.mode = fallback;
            reader.requests = new Map();
            reader.restoring = true;
            await this.loadContinuousReaderAt(reader.currentMarker, reader.currentMarker?.chapter_id);
        }
        if (reader.mode === 'side_by_side') return;
        this.setContinuousReaderStatus('Side-by-Side is available on screens 1024px wide or larger.');
        this.setupContinuousReaderChrome();
    },

    async loadContinuousReaderAt(marker = null, chapterId = null) {
        const reader = this.continuousReader;
        if (!reader?.active) return;
        const descriptors = reader.manifest.segments.filter(segment => segment.mode === reader.mode);
        let descriptor = marker ? descriptors.find(segment => marker.ordinal >= segment.first_unit_ordinal && marker.ordinal <= segment.last_unit_ordinal) : null;
        if (!descriptor && chapterId) {
            descriptor = await this.findContinuousSegmentForChapter(descriptors, chapterId);
        }
        descriptor ||= descriptors[0];
        if (!descriptor) return;
        const loaded = await this.fetchContinuousSegment(descriptor.id);
        if (!loaded) return;
        const nextDescriptor = descriptors.find(item => item.ordinal === descriptor.ordinal + 1);
        const next = nextDescriptor ? await this.fetchContinuousSegment(nextDescriptor.id, true) : null;
        reader.currentSegmentId = descriptor.id;
        reader.segmentIds = [loaded.id, next?.id].filter(Boolean);
        this.renderContinuousSegments([loaded, next].filter(Boolean), marker);
    },

    async findContinuousSegmentForChapter(descriptors, chapterId) {
        for (const descriptor of descriptors) {
            const segment = await this.fetchContinuousSegment(descriptor.id, true);
            if (segment?.units?.some(unit => Number(unit.chapter_id) === Number(chapterId))) return descriptor;
        }
        return null;
    },

    async fetchContinuousSegment(segmentId, prefetch = false) {
        const reader = this.continuousReader;
        if (!reader?.active) return null;
        reader.requests ||= new Map();
        if (reader.requests.has(segmentId)) return reader.requests.get(segmentId);
        const request = fetch(`${this.apiBase}/reader/books/${this.currentBook.id}/segments/${encodeURIComponent(segmentId)}?mode=${reader.mode}`)
            .then(response => response.ok ? response.json() : Promise.reject(new Error('segment unavailable')))
            .then(data => {
                window.authModule?.cacheReaderSegment?.(this.currentBook.id, data.segment).catch(() => {});
                return data.segment;
            })
            .catch(error => {
                const cachedPromise = window.authModule?.getCachedReaderSegment?.(
                    this.currentBook.id, reader.manifest.content_version, reader.mode, segmentId,
                );
                if (!cachedPromise) {
                    if (!prefetch) this.setContinuousReaderStatus('The next section needs a connection.');
                    return null;
                }
                return cachedPromise.then(cached => {
                    if (cached) return cached;
                    if (!prefetch) this.setContinuousReaderStatus('The next section needs a connection.');
                    return null;
                });
            });
        reader.requests.set(segmentId, request);
        return request;
    },

    renderContinuousSegments(segments, restoreMarker = null) {
        const reader = this.continuousReader;
        const container = document.getElementById('continuous-reader-content');
        if (!reader?.active || !container) return;
        reader.unitsById = new Map();
        const html = [];
        let activeChapter = null;
        for (const segment of segments) {
            for (const unit of segment.units) {
                reader.unitsById.set(unit.id, unit);
                if (unit.chapter_id !== activeChapter) {
                    activeChapter = unit.chapter_id;
                    html.push(`<h2 class="reader-chapter-heading" data-reader-chapter="${unit.chapter_id}">${this.escapeHtml(unit.chapter_title || `Chapter ${unit.chapter_number || ''}`)}</h2>`);
                }
                if (reader.mode === 'side_by_side') {
                    const original = unit.members.original;
                    const plain = unit.members.plain;
                    const cell = (member, label) => member?.available
                        ? `<p>${this.escapeHtml(member.content || '')}</p>`
                        : `<p class="reader-gap">${label} unavailable for this section.</p>`;
                    html.push(`<div class="side-by-side-row reader-alignment-row" data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="${unit.canonical_word_count || 0}"><div class="side-by-side-cell original">${cell(original, 'Original')}</div><div class="side-by-side-cell modern">${cell(plain, 'Plain English')}</div></div>`);
                } else if (unit.availability === 'gap') {
                    html.push(`<div class="reader-gap" data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="0">Plain English unavailable for this section.</div>`);
                } else {
                    html.push(`<p data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="${unit.word_count || 0}">${this.escapeHtml(unit.content || '')}</p>`);
                }
            }
        }
        container.className = `continuous-reader-content ${reader.mode === 'side_by_side' ? 'chapter-side-by-side' : ''}`;
        container.innerHTML = reader.mode === 'side_by_side'
            ? `<div class="side-by-side-headers"><div class="side-by-side-header">Original</div><div class="side-by-side-header">Plain English</div></div>${html.join('')}`
            : html.join('');
        this.pagination.originalContent = {};
        this.initializePagination(container, reader.mode === 'side_by_side' ? 'side-by-side' : reader.mode);
        if (restoreMarker?.paragraph_id) {
            const page = this.findContinuousPageForMarker(restoreMarker);
            if (page >= 0) {
                this.pagination.currentPage = page;
                this.displayCurrentPage();
            }
        }
        reader.restoring = false;
        // Opening/restoring never writes progress, but the chrome still needs
        // the marker that is visibly on screen for the next deliberate turn.
        this.settleContinuousReaderMarker();
    },

    findContinuousPageForMarker(marker) {
        const reader = this.continuousReader;
        const unit = reader?.unitsById?.get(marker.paragraph_id);
        const totalWords = unit?.word_count || unit?.canonical_word_count || 0;
        const targetWords = totalWords * Math.max(0, Math.min(1, Number(marker.offset) || 0));
        let accumulated = 0;
        for (let index = 0; index < this.pagination.pages.length; index += 1) {
            const page = document.createElement('div');
            page.innerHTML = this.pagination.pages[index];
            const fragments = [...page.querySelectorAll('[data-reader-anchor]')]
                .filter(candidate => candidate.dataset.readerAnchor === marker.paragraph_id);
            if (!fragments.length) continue;
            const words = fragments.reduce((sum, candidate) => {
                const text = reader.mode === 'side_by_side'
                    ? (candidate.querySelector('.side-by-side-cell.original')?.textContent || candidate.textContent || '')
                    : candidate.textContent || '';
                return sum + text.trim().split(/\s+/).filter(Boolean).length;
            }, 0);
            if (!totalWords || targetWords < accumulated + words || index === this.pagination.pages.length - 1) return index;
            accumulated += words;
        }
        return -1;
    },

    settleContinuousReaderMarker() {
        const reader = this.continuousReader;
        const page = this.pagination.activeWrapper?.querySelector('.pagination-page-container');
        const anchor = page?.querySelector('[data-reader-anchor]');
        if (!reader?.active || !anchor) return;
        reader.currentMarker = {
            book_id: this.currentBook.id, mode: reader.mode,
            content_version: reader.manifest.content_version, chapter_id: Number(anchor.dataset.readerChapter),
            paragraph_id: anchor.dataset.readerAnchor, offset: this.continuousMarkerOffset(anchor),
            quote: (anchor.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 180),
            ordinal: Number(anchor.dataset.readerOrdinal),
        };
        reader.currentMarker.word_position = this.continuousMarkerWordPosition(reader.currentMarker);
        reader.lastDisplayedOrdinal = reader.currentMarker.ordinal;
        const chapter = reader.manifest.structure.find(item => Number(item.chapter_id) === reader.currentMarker.chapter_id);
        document.getElementById('reader-chapter-title').textContent = chapter?.title || '';
        document.getElementById('continuous-reader-chapter-context').textContent = chapter?.title || '';
        this.updateContinuousReaderProgress();
    },

    continuousMarkerOffset(anchor) {
        const reader = this.continuousReader;
        const totalWords = Number(anchor?.dataset.readerWordCount) || reader?.unitsById?.get(anchor?.dataset.readerAnchor)?.word_count || 0;
        if (!anchor || totalWords <= 0 || !this.pagination?.pages?.length) return 0;
        const countWords = element => {
            const source = reader.mode === 'side_by_side'
                ? (element.querySelector('.side-by-side-cell.original')?.textContent || element.textContent || '')
                : element.textContent || '';
            return source.trim().split(/\s+/).filter(Boolean).length;
        };
        let priorWords = 0;
        for (let index = 0; index < this.pagination.currentPage; index += 1) {
            const page = document.createElement('div');
            page.innerHTML = this.pagination.pages[index];
            page.querySelectorAll('[data-reader-anchor]').forEach(candidate => {
                if (candidate.dataset.readerAnchor === anchor.dataset.readerAnchor) priorWords += countWords(candidate);
            });
        }
        return Math.max(0, Math.min(0.99, priorWords / totalWords));
    },

    continuousMarkerWordPosition(marker) {
        const reader = this.continuousReader;
        const direct = Number(marker?.word_position);
        if (Number.isFinite(direct)) return direct;
        const unit = reader?.unitsById?.get(marker?.paragraph_id);
        const wordStart = Number(unit?.word_start);
        const wordCount = Number(unit?.canonical_word_count ?? unit?.word_count);
        const offset = Math.max(0, Math.min(1, Number(marker?.offset) || 0));
        if (Number.isFinite(wordStart) && Number.isFinite(wordCount)) {
            return wordStart + (wordCount * offset);
        }
        const mode = reader?.manifest?.modes?.find(item => item.mode === reader.mode);
        const ordinal = Number(marker?.ordinal);
        if (mode?.total_word_count && mode?.unit_count && Number.isFinite(ordinal)) {
            return Math.max(0, Math.min(mode.total_word_count, (ordinal + offset) * mode.total_word_count / mode.unit_count));
        }
        return 0;
    },

    setupContinuousReaderChrome() {
        const reader = this.continuousReader;
        if (!reader?.active) return;
        document.getElementById('reader-book-title').textContent = this.currentBook.title;
        document.getElementById('reader-mode-settings')?.classList.remove('hidden');
        document.querySelectorAll('[data-reader-settings-mode]').forEach(button => {
            const manifest = reader.manifest.modes.find(item => item.mode === button.dataset.readerSettingsMode);
            const enabled = !!manifest && manifest.availability !== 'unavailable' &&
                this.isContinuousReaderModeAvailable(button.dataset.readerSettingsMode);
            button.disabled = !enabled;
            button.classList.toggle('active', button.dataset.readerSettingsMode === reader.mode);
            button.setAttribute('aria-pressed', button.dataset.readerSettingsMode === reader.mode ? 'true' : 'false');
            button.onclick = async () => {
                await this.switchContinuousReaderMode(button.dataset.readerSettingsMode);
                this.setupContinuousReaderChrome();
            };
        });
        const sideBySide = reader.manifest.modes.find(item => item.mode === 'side_by_side');
        const modeHelp = document.getElementById('reader-mode-help');
        if (modeHelp) {
            modeHelp.textContent = sideBySide?.availability === 'unavailable'
                ? 'Side-by-Side is unavailable for this book.'
                : 'Side-by-Side is available on screens 1024px wide or larger.';
        }
        document.getElementById('reader-back-button').onclick = async () => {
            await this.saveContinuousReader('navigation');
            reader.active = false;
            document.getElementById('reading-settings-panel')?.classList.add('hidden');
            await this.selectBook(this.currentBook);
        };
        document.getElementById('reader-toc-button').onclick = () => this.toggleContinuousPanel('reader-toc-panel');
        document.getElementById('reader-settings-button').onclick = () => {
            document.getElementById('reader-toc-panel')?.classList.add('hidden');
            document.getElementById('reader-toc-button')?.setAttribute('aria-expanded', 'false');
            document.getElementById('reading-settings-panel')?.classList.remove('hidden');
        };
        document.querySelectorAll('[data-reader-close]').forEach(button => button.onclick = () => {
            document.getElementById(button.dataset.readerClose)?.classList.add('hidden');
            document.getElementById('reader-toc-button')?.setAttribute('aria-expanded', 'false');
        });
        const toc = document.getElementById('reader-toc-list');
        toc.innerHTML = reader.manifest.structure.filter(entry => entry.kind === 'chapter').map(entry =>
            `<button type="button" data-reader-chapter-target="${entry.chapter_id}">${this.escapeHtml(entry.title)}</button>`).join('');
        toc.querySelectorAll('[data-reader-chapter-target]').forEach(button => button.onclick = async () => {
            document.getElementById('reader-toc-panel').classList.add('hidden');
            document.getElementById('reader-toc-button')?.setAttribute('aria-expanded', 'false');
            reader.restoring = true;
            await this.loadContinuousReaderAt(null, button.dataset.readerChapterTarget);
            await this.saveContinuousReader('toc');
        });
    },

    setupContinuousReaderLifecycle() {
        if (this.continuousReaderLifecycleBound) return;
        this.continuousReaderLifecycleBound = true;
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') this.saveContinuousReader('hidden');
        });
        window.addEventListener('pagehide', () => this.saveContinuousReader('pagehide'));
        const enforceViewport = () => this.enforceContinuousReaderViewport();
        window.addEventListener('resize', enforceViewport);
        window.matchMedia('(max-width: 1023px)').addEventListener?.('change', enforceViewport);
        window.setInterval(() => {
            const reader = this.continuousReader;
            if (reader?.active && document.visibilityState === 'visible' && Date.now() - reader.pageTurnAt >= 15000) {
                this.saveContinuousReader('page_turn', 0, 15);
                reader.pageTurnAt = Date.now();
            }
        }, 15000);
    },

    toggleContinuousPanel(id) {
        const panel = document.getElementById(id);
        panel?.classList.toggle('hidden');
        if (id === 'reader-toc-panel') {
            document.getElementById('reader-toc-button')?.setAttribute('aria-expanded', panel?.classList.contains('hidden') ? 'false' : 'true');
        }
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

    async mapContinuousMarker(marker, fromMode, toMode) {
        if (!marker || fromMode === toMode) return marker;
        try {
            const response = await fetch(`${this.apiBase}/reader/books/${this.currentBook.id}/map`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ marker: { ...marker, mode: fromMode }, target_mode: toMode }),
            });
            const data = await response.json();
            return response.ok && data.success ? data.marker : null;
        } catch (_) {
            return null;
        }
    },

    async recoverContinuousMarker(marker) {
        try {
            const response = await fetch(`${this.apiBase}/reader/books/${this.currentBook.id}/recover`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ marker }),
            });
            const data = await response.json();
            if (response.ok && data.success) {
                return data.marker;
            }
        } catch (_) { /* retain original marker as a best-effort entry */ }
        return null;
    },

    onContinuousPageDisplayed() {
        const reader = this.continuousReader;
        if (!reader?.active || reader.restoring) return;
        const page = this.pagination.activeWrapper?.querySelector('.pagination-page-container');
        const anchor = page?.querySelector('[data-reader-anchor]');
        if (!anchor) return;
        const marker = {
            book_id: this.currentBook.id, mode: reader.mode,
            content_version: reader.manifest.content_version, chapter_id: Number(anchor.dataset.readerChapter),
            paragraph_id: anchor.dataset.readerAnchor, offset: this.continuousMarkerOffset(anchor),
            quote: (anchor.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 180),
            ordinal: Number(anchor.dataset.readerOrdinal),
        };
        marker.word_position = this.continuousMarkerWordPosition(marker);
        const sequential = reader.lastDisplayedOrdinal !== null && marker.ordinal === reader.lastDisplayedOrdinal + 1;
        const activeSeconds = document.visibilityState === 'visible'
            ? Math.min(60, Math.floor((Date.now() - reader.pageTurnAt) / 1000)) : 0;
        reader.pageTurnAt = Date.now();
        reader.lastDisplayedOrdinal = marker.ordinal;
        reader.currentMarker = marker;
        const chapter = reader.manifest.structure.find(item => Number(item.chapter_id) === marker.chapter_id);
        document.getElementById('reader-chapter-title').textContent = chapter?.title || '';
        document.getElementById('continuous-reader-chapter-context').textContent = chapter?.title || '';
        this.updateContinuousReaderProgress();
        clearTimeout(reader.settleTimer);
        reader.settleTimer = setTimeout(() => this.saveContinuousReader('page_turn', sequential ? 1 : 0, activeSeconds), 600);
        const modeManifest = reader.manifest.modes.find(item => item.mode === reader.mode);
        clearTimeout(reader.terminalTimer);
        if (modeManifest?.terminal_paragraph_id === marker.paragraph_id && sequential) {
            reader.terminalTimer = setTimeout(() => this.saveContinuousReader('completion', 0, 2, {
                terminal_dwell_ms: 2000, sequential_terminal_entry: true,
            }), 2000);
        }
    },

    async saveContinuousReader(cause, boundaries = 0, activeSeconds = 0, extra = {}) {
        const reader = this.continuousReader;
        if (!reader?.active || !reader.currentMarker || reader.restoring) return;
        const furthest = reader.furthestMarker;
        const qualified = boundaries > 0 && (!furthest || reader.currentMarker.ordinal >= furthest.ordinal)
            ? reader.currentMarker : null;
        if (qualified) reader.furthestMarker = qualified;
        const modeState = reader.state?.modes?.find(item => item.mode === reader.mode);
        await window.authModule?.queueReaderMutation?.({
            book_id: this.currentBook.id, mode: reader.mode, current_marker: reader.currentMarker,
            qualified_furthest_marker: qualified, event_cause: cause,
            active_seconds_delta: activeSeconds, sequential_boundaries_delta: boundaries,
            base_revision: modeState?.revision || modeState?.server_revision || 0,
            ...extra,
        });
        this.updateContinuousReaderProgress();
    },

    updateContinuousReaderProgress() {
        const reader = this.continuousReader;
        const mode = reader?.manifest?.modes?.find(item => item.mode === reader.mode);
        const marker = reader?.furthestMarker;
        const wordPosition = this.continuousMarkerWordPosition(marker);
        const percentage = mode?.total_word_count && marker
            ? Math.min(99, Math.max(0, Math.round(wordPosition * 100 / mode.total_word_count)))
            : 0;
        const text = document.getElementById('continuous-reader-progress');
        if (text) text.textContent = `${percentage}%`;
    },

    setContinuousReaderStatus(message) {
        const status = document.getElementById('reader-status');
        if (status) { status.textContent = message; status.classList.remove('hidden'); }
    },

    async navigateContinuousSegment(direction) {
        const reader = this.continuousReader;
        if (!reader?.active) return;
        const segment = await this.fetchContinuousSegment(reader.currentSegmentId);
        const id = direction > 0 ? segment?.next_segment_id : segment?.previous_segment_id;
        if (!id) return;
        reader.restoring = false;
        const loaded = await this.fetchContinuousSegment(id);
        if (!loaded) return;
        reader.currentSegmentId = id;
        this.renderContinuousSegments([loaded], null);
    },
};
