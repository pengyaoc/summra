// Reading-experience settings: font/size/theme picker, sticky chapter
// header (original + medium/summary variants), and reading-progress bars.
//
// Extracted from app.js's single SummraApp class (2026-09 refactor) as a
// plain object of methods, merged onto SummraApp.prototype via
// Object.assign in app.js — see pagination.js's header comment and
// frontend/static/js/README.md for why (structural move only, `this`
// unaffected by which file a method's source lives in).
export const settingsMixin = {
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
    },

    applyFont(font) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');
        if (chapterSection) {
            chapterSection.setAttribute('data-font', font);
        }
        if (mediumSection) {
            mediumSection.setAttribute('data-font', font);
        }

        // Reinitialize pagination if active (check for pagination wrapper existence)
        const paginationWrapper = document.querySelector('.pagination-wrapper');
        if (!paginationWrapper) {
            return;
        }

        const currentViewMode = this.getCurrentViewMode();
        const parentContainer = paginationWrapper.parentElement;
        if (!parentContainer) {
            return;
        }

        this.clearPagination();

        // Restore each view container from the snapshot taken before pagination
        // wrapped them. originalContent holds the correctly-formatted HTML for
        // whichever containers have been paginated this session — including
        // side-by-side, which was built from raw chapter text in showChapterDetail.
        const fullTextEl = document.getElementById('chapter-fulltext');
        const modernEnglishEl = document.getElementById('chapter-modern-english');
        const sideBySideEl = document.getElementById('chapter-side-by-side');

        if (this.pagination.originalContent) {
            if (this.pagination.originalContent['chapter-fulltext'] && fullTextEl) {
                fullTextEl.innerHTML = this.pagination.originalContent['chapter-fulltext'];
            }
            if (this.pagination.originalContent['chapter-modern-english'] && modernEnglishEl) {
                modernEnglishEl.innerHTML = this.pagination.originalContent['chapter-modern-english'];
            }
            if (this.pagination.originalContent['chapter-side-by-side'] && sideBySideEl) {
                sideBySideEl.innerHTML = this.pagination.originalContent['chapter-side-by-side'];
            }
        }

        const containerToPaginate = this.applyChapterViewMode(currentViewMode);
        if (containerToPaginate) {
            this.initializePagination(containerToPaginate, currentViewMode, this.currentIllustrationData);
        }
    },

    applyFontSize(size) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');

        if (chapterSection) {
            const fulltext = chapterSection.querySelector('.chapter-fulltext');
            const modernEnglish = chapterSection.querySelector('.chapter-modern-english');
            const sideBySideCells = chapterSection.querySelectorAll('.side-by-side-cell');
            const summaryText = chapterSection.querySelector('.chapter-summary-text');
            const summaryContentText = chapterSection.querySelector('#chapter-summary-content .summary-text');

            // Apply to pagination containers (when pagination is active)
            const paginationContainers = chapterSection.querySelectorAll('.pagination-page-container');

            if (fulltext) fulltext.style.fontSize = `${size}px`;
            if (modernEnglish) modernEnglish.style.fontSize = `${size}px`;
            if (sideBySideCells.length > 0) {
                sideBySideCells.forEach(cell => {
                    cell.style.fontSize = `${size}px`;
                });
            }
            if (summaryText) summaryText.style.fontSize = `${size}px`;
            if (summaryContentText) summaryContentText.style.fontSize = `${size}px`;

            // Apply to paginated content
            if (paginationContainers.length > 0) {
                paginationContainers.forEach(container => {
                    container.style.fontSize = `${size}px`;
                });
            }
        }

        if (mediumSection) {
            const mediumText = mediumSection.querySelector('.summary-text');
            if (mediumText) mediumText.style.fontSize = `${size}px`;

            // Apply to pagination containers (when pagination is active)
            const paginationContainers = mediumSection.querySelectorAll('.pagination-page-container');
            if (paginationContainers.length > 0) {
                paginationContainers.forEach(container => {
                    container.style.fontSize = `${size}px`;
                });
            }
        }
    },

    applyTheme(theme) {
        const chapterSection = document.getElementById('chapter-detail-section');
        const mediumSection = document.getElementById('medium-detail-section');
        if (chapterSection) {
            chapterSection.setAttribute('data-theme', theme);
        }
        if (mediumSection) {
            mediumSection.setAttribute('data-theme', theme);
        }
    },

    saveReadingPreference(key, value) {
        try {
            localStorage.setItem(`reading_${key}`, value);

            // Recalculate pagination when font or size changes affect layout
            if (key === 'font' || key === 'fontSize') {
                setTimeout(() => {
                    if (this.pagination.totalPages > 0) {
                        this.recalculatePagination();
                    }
                }, 100);
            }
        } catch (error) {
            console.error('Error saving reading preference:', error);
        }
    },

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
    },

    updateReadingProgress() {
        // Skip if pagination is active - pagination has its own progress tracking
        if (this.pagination && this.pagination.totalPages > 0) {
            return;
        }

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
    },

    setupStickyHeader() {
        const stickyHeader = document.getElementById('sticky-reading-header');

        // Show sticky header when chapter section is visible
        const observer = new MutationObserver(() => {
            // Skip sticky header updates during chapter boundary navigation to prevent flicker
            if (this.isChapterBoundaryNavigation) {
                return;
            }

            const chapterSection = document.getElementById('chapter-detail-section');
            if (chapterSection && !chapterSection.classList.contains('hidden')) {
                // Chapter is visible - show sticky header immediately (no scroll needed)
                if (stickyHeader) {
                    stickyHeader.classList.remove('hidden');
                }
            } else {
                // Chapter is hidden - hide sticky header
                if (stickyHeader) {
                    stickyHeader.classList.add('hidden');
                }
            }
        });

        // Observe chapter section visibility changes
        const chapterSection = document.getElementById('chapter-detail-section');
        if (chapterSection) {
            observer.observe(chapterSection, { attributes: true, attributeFilter: ['class'] });

            // Initial check
            if (!chapterSection.classList.contains('hidden') && stickyHeader) {
                stickyHeader.classList.remove('hidden');
            }
        }
    },

    updateStickyHeaderTitle(bookTitle, chapterNum = null, chapterTitle = '') {
        // New sticky header uses dropdown - update the short title
        const stickyShortTitle = document.getElementById('sticky-chapter-title-short');

        if (stickyShortTitle && chapterNum) {
            // Format as "Chapter X: Title" or just "Chapter X"
            const displayText = chapterTitle
                ? `${chapterNum}. ${chapterTitle}`
                : `Chapter ${chapterNum}`;
            stickyShortTitle.textContent = displayText;
        }
    },

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
    },

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

};
