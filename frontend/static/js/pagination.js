// Pagination engine: page-based chapter reading (split original/plain-
// English/side-by-side text into fixed-height pages, illustration pages,
// touch/wheel/keyboard navigation, position persistence).
//
// Extracted from app.js's single SummraApp class (2026-09 refactor) as a
// plain object of methods, merged onto SummraApp.prototype via
// Object.assign in app.js. This is a structural move only: every method
// keeps referencing `this.pagination`, `this.currentBook`, etc. exactly as
// before, and every cross-call (e.g. this.navigateToNextPage() calling
// this.recalculatePagination()) keeps working unchanged, because
// Object.assign puts these methods on the exact same prototype as the rest
// of SummraApp's methods — `this` is unaffected by which file a method's
// source lives in.
export const paginationMixin = {
    // ========================================
    // PAGINATION SYSTEM FOR CHAPTER READING
    // ========================================

    /**
     * Setup pagination system for page-based reading experience
     */
    setupPagination() {
        // Setup keyboard navigation
        document.addEventListener('keydown', (e) => {
            // The continuous reader preserves the established page-turn keys.
            const chapterSection = document.getElementById('chapter-detail-section');
            const continuousActive = this.continuousReader?.active;
            if ((!chapterSection || chapterSection.classList.contains('hidden')) && !continuousActive) {
                return;
            }

            // Ignore if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                this.navigateToPreviousPage();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                this.navigateToNextPage();
            }
        });

        // Handle window resize - recalculate pages
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (this.pagination.totalPages > 0) {
                    this.recalculatePagination();
                }
            }, 300);
        });

        // Handle wheel events for scroll-to-turn-page
        const handleWheel = (e) => {
            const chapterSection = document.getElementById('chapter-detail-section');
            if ((!chapterSection || chapterSection.classList.contains('hidden')) && !this.continuousReader?.active) {
                return;
            }

            // Only prevent default if we're actively paginating
            if (this.pagination.totalPages > 0) {
                e.preventDefault();

                // Debounce rapid scroll events
                clearTimeout(this.pagination.wheelTimeout);
                this.pagination.wheelTimeout = setTimeout(() => {
                    if (e.deltaY > 0) {
                        // Scrolling down = next page
                        this.navigateToNextPage();
                    } else if (e.deltaY < 0) {
                        // Scrolling up = previous page
                        this.navigateToPreviousPage();
                    }
                }, 100);
            }
        };

        // Attach with passive: false to allow preventDefault
        document.addEventListener('wheel', handleWheel, { passive: false });
        this.pagination.wheelHandler = handleWheel;
    },

    /**
     * Initialize pagination for current chapter text
     */
    initializePagination(containerElement, viewMode = 'original', illustrationData = null) {
        if (!containerElement || !this.pagination.enabled) {
            return;
        }

        // Prevent re-entry while pagination is initializing
        if (this.pagination.isInitializing) {
            console.log('[Pagination] Already initializing, skipping...');
            return;
        }

        this.pagination.isInitializing = true;
        console.log('[Pagination] Starting initialization...');

        // Store current view mode and illustration data
        this.pagination.currentViewMode = viewMode;
        this.pagination.illustrationData = illustrationData;

        // Get the actual text content before any wrapper manipulation
        let textContent;
        const existingWrapper = containerElement.querySelector('.pagination-wrapper');
        if (existingWrapper) {
            // Check if we have the original content stored
            const containerId = containerElement.id;
            if (this.pagination.originalContent && this.pagination.originalContent[containerId]) {
                // Use stored original content
                textContent = this.pagination.originalContent[containerId];
            } else {
                // Fallback: try to get from container (this shouldn't happen normally)
                textContent = containerElement.innerHTML;
            }
            // Remove the old wrapper
            existingWrapper.remove();
        } else {
            // No existing wrapper, get content directly and store it
            textContent = containerElement.innerHTML;

            // Store original content for this container
            if (!this.pagination.originalContent) {
                this.pagination.originalContent = {};
            }
            const containerId = containerElement.id;
            this.pagination.originalContent[containerId] = textContent;
        }

        // Create new pagination wrapper
        const paginationWrapper = document.createElement('div');
        paginationWrapper.className = 'pagination-wrapper';
        containerElement.innerHTML = '';
        containerElement.appendChild(paginationWrapper);

        // Create page container for measuring
        const pageContainer = document.createElement('div');
        pageContainer.className = 'pagination-page-container';
        // Copy original container's classes to preserve side-by-side detection
        if (containerElement.classList.contains('chapter-side-by-side')) {
            pageContainer.classList.add('chapter-side-by-side');
        }
        // Copy the active reader's font setting for page measurement/rendering.
        const readerSectionEl = this.continuousReader?.active
            ? document.getElementById('continuous-reader-section')
            : document.getElementById('chapter-detail-section');
        if (readerSectionEl && readerSectionEl.hasAttribute('data-font')) {
            pageContainer.setAttribute('data-font', readerSectionEl.getAttribute('data-font'));
        }
        pageContainer.innerHTML = textContent;
        paginationWrapper.appendChild(pageContainer);

        // Store reference to current active wrapper
        this.pagination.activeWrapper = paginationWrapper;

        // Prevent body scrolling when pagination is active.
        // iOS Safari/Chrome (WebKit) can keep scrolling the <html> element via
        // elastic/momentum overscroll even when only <body> has overflow:hidden,
        // which lets residual scroll settle a few px off after the scrollTo(0)
        // in displayCurrentPage() and cuts off the first line under the sticky
        // header. Lock both elements.
        document.documentElement.classList.add('pagination-active');
        document.documentElement.style.overflow = 'hidden';
        document.body.classList.add('pagination-active');
        document.body.style.overflow = 'hidden';

        // Calculate pages based on viewport height (will prepend illustration if available)
        this.calculatePages(pageContainer);

        // Setup navigation zones
        this.setupNavigationZones(paginationWrapper);

        // Setup touch gestures
        this.setupTouchGestures(paginationWrapper);

        // Check if we should go to last page (when navigating from next chapter)
        if (this.pagination.shouldGoToLastPage) {
            console.log(`🔍 shouldGoToLastPage flag is true, totalPages: ${this.pagination.totalPages}`);
            this.pagination.currentPage = this.pagination.totalPages - 1;
            console.log(`📍 Set currentPage to last page: ${this.pagination.currentPage}`);
            this.pagination.shouldGoToLastPage = false;
        } else if (this.pagination.shouldResetToPage1) {
            // Reset to page 1 when switching view modes
            this.pagination.currentPage = 0;
            this.pagination.shouldResetToPage1 = false;
        } else {
            // Load saved page position
            const savedPage = this.loadPagePosition();
            this.pagination.currentPage = savedPage;
        }

        // Display current page
        this.displayCurrentPage();

        // Update progress indicator
        this.updatePaginationProgress();

        // Reapply saved font size to pagination container (fixes font size not applying after pagination wraps content)
        const savedFontSize = localStorage.getItem('reading_fontSize') || '16';
        this.applyFontSize(savedFontSize);

        // Show chapter section after pagination is complete (prevents flash of unpaginated content)
        const chapterSection = document.getElementById('chapter-detail-section');
        if (chapterSection) {
            chapterSection.style.visibility = 'visible';
        }

        // Clear initialization flag
        this.pagination.isInitializing = false;
        console.log('[Pagination] Initialization complete');
    },

    /**
     * Calculate pages using incremental DOM algorithm (Amazon/ebook-paginator style)
     * No measurements, no safety margins - uses browser's native scrollHeight detection
     */
    calculatePages(containerElement) {
        console.log('[calculatePages] Starting...');
        console.log('[calculatePages] Container element:', containerElement?.id, containerElement?.className);

        // Get EXACT viewport height minus all fixed elements
        const viewportHeight = window.innerHeight;
        const stickyHeaderHeight = this.continuousReader?.active
            ? (document.querySelector('.continuous-reader-chrome')?.offsetHeight || 52) + 51
            : (document.querySelector('.sticky-reading-header')?.offsetHeight || 51);
        const progressBarHeight = this.continuousReader?.active
            ? (document.querySelector('.continuous-reader-footer')?.offsetHeight || 30)
            : (document.querySelector('.reading-progress-bar')?.offsetHeight || 30);
        const verticalPadding = 20;

        this.pagination.containerHeight = viewportHeight - stickyHeaderHeight - progressBarHeight - verticalPadding;
        console.log('[calculatePages] Container height:', this.pagination.containerHeight);

        // Set wrapper height to match calculated height
        const wrapper = containerElement.closest('.pagination-wrapper');
        if (wrapper) {
            wrapper.style.height = `${this.pagination.containerHeight}px`;
            wrapper.style.maxHeight = `${this.pagination.containerHeight}px`;
        }

        // Get all block elements (paragraphs, headings, lists, etc.)
        // For side-by-side view, treat each row as an atomic block
        let blocks;
        // Side-by-side: pull the column-headers banner out of the paginated
        // blocks so it doesn't consume a whole page by itself. We re-prepend
        // its HTML to every page below, and shrink the per-page budget by its
        // height so the rows still fit underneath.
        let sxsHeadersHTML = '';
        if (containerElement.classList.contains('chapter-side-by-side')) {
            const headersEl = containerElement.querySelector('.side-by-side-headers');
            if (headersEl) {
                sxsHeadersHTML = headersEl.outerHTML;
                this.pagination.containerHeight -= headersEl.offsetHeight;
            }
            // For side-by-side view: rows are the atomic blocks
            blocks = Array.from(containerElement.querySelectorAll('.side-by-side-row'));
            console.log('[calculatePages] Side-by-side mode, found blocks:', blocks.length,
                        'headers pulled out:', !!sxsHeadersHTML,
                        'adjusted containerHeight:', this.pagination.containerHeight);
        } else {
            // For regular views: use paragraphs and headings as blocks
            blocks = Array.from(containerElement.querySelectorAll('p, h1, h2, h3, h4, h5, h6, blockquote, pre, ul, ol'));
            console.log('[calculatePages] Regular mode, found blocks:', blocks.length);
        }

        if (blocks.length === 0) {
            console.log('[calculatePages] No blocks found, using entire content as one page');
            this.pagination.pages = [containerElement.innerHTML];
            this.pagination.totalPages = 1;
            return;
        }

        console.log('[calculatePages] Starting page calculation loop...');

        // Get computed styles from the container being measured
        const computedStyle = window.getComputedStyle(containerElement);

        // Create page container with EXACT same styles as the real container
        // This ensures scrollHeight measurements are accurate
        const createPageContainer = () => {
            const pageDiv = document.createElement('div');
            pageDiv.className = 'pagination-page-container';
            // Copy chapter-side-by-side class if present (needed for grid CSS)
            if (containerElement.classList.contains('chapter-side-by-side')) {
                pageDiv.classList.add('chapter-side-by-side');
            }
            // Copy active reader font setting for an accurate measurement node.
            const readerSectionEl = this.continuousReader?.active
                ? document.getElementById('continuous-reader-section')
                : document.getElementById('chapter-detail-section');
            if (readerSectionEl && readerSectionEl.hasAttribute('data-font')) {
                pageDiv.setAttribute('data-font', readerSectionEl.getAttribute('data-font'));
            }
            pageDiv.style.cssText = `
                position: absolute;
                visibility: hidden;
                left: -9999px;
                width: ${containerElement.offsetWidth}px;
                height: ${this.pagination.containerHeight}px;
                max-height: ${this.pagination.containerHeight}px;
                overflow: hidden;
                font-family: ${computedStyle.fontFamily};
                font-size: ${computedStyle.fontSize};
                line-height: ${computedStyle.lineHeight};
                padding: ${computedStyle.padding};
                box-sizing: ${computedStyle.boxSizing};
            `;
            document.body.appendChild(pageDiv);
            return pageDiv;
        };

        const pages = [];
        let blockIndex = 0;
        let safetyCounter = 0;
        const maxIterations = blocks.length * 3; // Safety: no more than 3x the number of blocks

        // Incremental algorithm: Build one page at a time
        while (blockIndex < blocks.length) {
            safetyCounter++;
            if (safetyCounter > maxIterations) {
                console.error('[calculatePages] INFINITE LOOP DETECTED! Breaking out. blockIndex:', blockIndex, 'blocks.length:', blocks.length);
                break;
            }

            if (safetyCounter % 10 === 0) {
                console.log('[calculatePages] Progress:', safetyCounter, 'pages created:', pages.length, 'blockIndex:', blockIndex, '/', blocks.length);
            }

            const pageDiv = createPageContainer();
            const pageBlocks = [];

            // Add blocks until overflow
            let innerSafetyCounter = 0;
            while (blockIndex < blocks.length) {
                innerSafetyCounter++;
                if (innerSafetyCounter > blocks.length) {
                    console.error('[calculatePages] INNER LOOP INFINITE! Breaking out.');
                    break;
                }
                const block = blocks[blockIndex];
                const clone = block.cloneNode(true);
                pageDiv.appendChild(clone);

                // Check for overflow using native scrollHeight (pixel-perfect!)
                if (pageDiv.scrollHeight > this.pagination.containerHeight) {
                    // Overflow detected - remove last block
                    pageDiv.removeChild(clone);

                    // Handle side-by-side rows - try to split them when needed
                    if (block.classList && block.classList.contains('side-by-side-row')) {
                        // If page is empty and row doesn't fit, try to split it
                        if (pageBlocks.length === 0) {
                            const splitResult = this.splitSideBySideRowToFit(block, pageDiv, this.pagination.containerHeight);

                            if (splitResult.firstRow) {
                                // Successfully split - add first part to current page
                                pageDiv.appendChild(splitResult.firstRow);
                                pageBlocks.push(splitResult.firstRow.outerHTML);

                                // Create remainder row for next page
                                const remainderRow = block.cloneNode(true);
                                remainderRow.querySelector('.side-by-side-cell.original p').innerHTML = splitResult.remainder.leftText;
                                remainderRow.querySelector('.side-by-side-cell.modern p').innerHTML = splitResult.remainder.rightText;

                                // Insert remainder as next block to process
                                blocks.splice(blockIndex + 1, 0, remainderRow);
                                blockIndex++;
                                break;
                            } else {
                                // Can't split - force entire row anyway
                                console.log('[calculatePages] Side-by-side row too large for page, forcing it');
                                pageDiv.appendChild(clone);
                                pageBlocks.push(block.outerHTML);
                                blockIndex++;
                                break;
                            }
                        }

                        // Otherwise, move entire row to next page
                        console.log('[calculatePages] Side-by-side row does not fit, moving to next page');
                        break;
                    }

                    // Try to split if it's a paragraph (regardless of page being empty or not)
                    if (block.tagName === 'P') {
                        const splitResult = this.splitParagraphToFit(block, pageDiv, this.pagination.containerHeight);

                        if (splitResult.firstPart) {
                            // Successfully split - add first part to current page
                            pageDiv.appendChild(splitResult.firstPart);
                            pageBlocks.push(splitResult.firstPart.outerHTML);

                            // Create remainder paragraph WITHOUT forcing visual separation
                            // The remainder will continue naturally on the next page
                            const remainderP = document.createElement('p');
                            remainderP.innerHTML = splitResult.remainder;
                            // Copy attributes from original to maintain styling
                            for (const attr of block.attributes) {
                                remainderP.setAttribute(attr.name, attr.value);
                            }
                            // Mark as continuation to remove top spacing (CSS handles this)
                            remainderP.classList.add('paragraph-continuation');

                            // Insert remainder as next block to process
                            blocks.splice(blockIndex + 1, 0, remainderP);
                            blockIndex++; // Move past the original block (remainder will be processed next)
                            break;
                        }
                    }

                    // If page is empty and block doesn't fit (and we couldn't split it), we have to force it
                    if (pageBlocks.length === 0) {
                        console.log('[calculatePages] Block too large for page, forcing it anyway:', block.tagName);
                        pageDiv.appendChild(clone);
                        pageBlocks.push(block.outerHTML);
                        blockIndex++;
                        break;
                    }

                    break; // Page is full
                }

                // No overflow - keep this block
                pageBlocks.push(block.outerHTML);
                blockIndex++;
            }

            // Save page content
            if (pageBlocks.length > 0) {
                pages.push(pageBlocks.join(''));
            }

            // Clean up page container
            document.body.removeChild(pageDiv);
        }

        // Store pages
        this.pagination.pages = pages.length > 0 ? pages : [containerElement.innerHTML];

        // Side-by-side: re-prepend the headers banner to every page so column
        // labels stay visible (and page 1 isn't just the banner alone).
        if (sxsHeadersHTML) {
            this.pagination.pages = this.pagination.pages.map((p) => sxsHeadersHTML + p);
        }

        // Prepend illustration as page 0 if available
        if (this.pagination.illustrationData) {
            const illustrationPage = this.createIllustrationPage(this.pagination.illustrationData);
            this.pagination.pages.unshift(illustrationPage);
        }

        this.pagination.totalPages = this.pagination.pages.length;
    },

    /**
     * Split paragraph to fit remaining space using binary search (O(log n))
     * Returns {firstPart: Element, remainder: String} or {firstPart: null}
     */
    splitParagraphToFit(paragraph, pageDiv, pageHeight) {
        const text = paragraph.textContent.trim();
        const words = text.split(/\s+/).filter(w => w.length > 0);

        if (words.length <= 1) {
            return { firstPart: null, remainder: null };
        }

        // Binary search for maximum words that fit
        let left = 1;
        let right = words.length - 1;
        let bestFit = 0;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const testText = words.slice(0, mid).join(' ');

            // Create test paragraph with same attributes
            const testP = document.createElement('p');
            testP.innerHTML = testText;
            for (const attr of paragraph.attributes) {
                testP.setAttribute(attr.name, attr.value);
            }

            // Test if it fits
            pageDiv.appendChild(testP);
            const fits = pageDiv.scrollHeight <= pageHeight;
            pageDiv.removeChild(testP);

            if (fits) {
                bestFit = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        if (bestFit === 0) {
            return { firstPart: null, remainder: null };
        }

        // Create the split result
        const firstPart = document.createElement('p');
        firstPart.innerHTML = words.slice(0, bestFit).join(' ');
        for (const attr of paragraph.attributes) {
            firstPart.setAttribute(attr.name, attr.value);
        }

        const remainder = words.slice(bestFit).join(' ');

        return { firstPart, remainder };
    },

    /**
     * Split side-by-side row to fit remaining space using dual binary search
     * Each column is measured independently, then uses minimum of both word counts
     * Returns {firstRow: Element, remainder: Object} or {firstRow: null}
     */
    splitSideBySideRowToFit(row, pageDiv, pageHeight) {
        const leftCell = row.querySelector('.side-by-side-cell.original p');
        const rightCell = row.querySelector('.side-by-side-cell.modern p');

        if (!leftCell || !rightCell) {
            return { firstRow: null, remainder: null };
        }

        const leftText = leftCell.textContent.trim();
        const rightText = rightCell.textContent.trim();
        const leftWords = leftText.split(/\s+/).filter(w => w.length > 0);
        const rightWords = rightText.split(/\s+/).filter(w => w.length > 0);

        if (leftWords.length <= 1 && rightWords.length <= 1) {
            return { firstRow: null, remainder: null };
        }

        // Binary search for each column independently
        const leftFit = this.binarySearchColumnFit(leftWords, rightWords, row, pageDiv, pageHeight, 'left');
        const rightFit = this.binarySearchColumnFit(rightWords, leftWords, row, pageDiv, pageHeight, 'right');

        // Use MINIMUM of both - stop where taller column would overflow
        const minFit = Math.min(leftFit, rightFit);

        if (minFit === 0) {
            return { firstRow: null, remainder: null };
        }

        // Create split row with first parts
        const firstRow = row.cloneNode(true);
        firstRow.querySelector('.side-by-side-cell.original p').innerHTML = leftWords.slice(0, minFit).join(' ');
        firstRow.querySelector('.side-by-side-cell.modern p').innerHTML = rightWords.slice(0, minFit).join(' ');

        // Create remainder data
        const remainder = {
            leftText: leftWords.slice(minFit).join(' '),
            rightText: rightWords.slice(minFit).join(' ')
        };

        return { firstRow, remainder };
    },

    /**
     * Binary search for max words that fit in ONE column of a side-by-side row
     * Tests with test text in target column and full text in other column
     */
    binarySearchColumnFit(targetWords, otherWords, row, pageDiv, pageHeight, side) {
        let left = 1;
        let right = targetWords.length;
        let bestFit = 0;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const testText = targetWords.slice(0, mid).join(' ');
            const fullText = otherWords.join(' ');

            // Create test row
            const testRow = row.cloneNode(true);

            if (side === 'left') {
                testRow.querySelector('.side-by-side-cell.original p').innerHTML = testText;
                testRow.querySelector('.side-by-side-cell.modern p').innerHTML = fullText;
            } else {
                testRow.querySelector('.side-by-side-cell.original p').innerHTML = fullText;
                testRow.querySelector('.side-by-side-cell.modern p').innerHTML = testText;
            }

            // Test if it fits
            pageDiv.appendChild(testRow);
            const fits = pageDiv.scrollHeight <= pageHeight;
            pageDiv.removeChild(testRow);

            if (fits) {
                bestFit = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        return bestFit;
    },

    /**
     * Create illustration page HTML (page 0)
     */
    createIllustrationPage(illustrationData) {
        return `
            <div class="illustration-page" style="
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                background: transparent;
                position: relative;
            ">
                <!-- Loading skeleton -->
                <div class="illustration-skeleton" style="
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    width: 80%;
                    height: 60%;
                    background: linear-gradient(90deg, #f0f0f0 0px, #e8e8e8 40px, #f0f0f0 80px);
                    background-size: 1000px 100%;
                    animation: shimmer 2s infinite linear;
                    border-radius: 8px;
                    z-index: 1;
                "></div>

                <picture style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; position: relative; z-index: 2;">
                    <source srcset="${illustrationData.webpUrl}" type="image/webp" />
                    <source srcset="${illustrationData.jpgUrl}" type="image/jpeg" />
                    <img
                        src="${illustrationData.jpgUrl}"
                        alt="${illustrationData.alt}"
                        style="
                            max-width: 100%;
                            max-height: 100%;
                            width: auto;
                            height: auto;
                            object-fit: contain;
                            cursor: pointer;
                            opacity: 0;
                            transition: opacity 0.3s ease-in;
                        "
                        onload="this.style.opacity='1'; this.closest('.illustration-page')?.querySelector('.illustration-skeleton')?.remove();"
                        onclick="window.summraApp?.openLightbox?.('${illustrationData.baseUrl}', '${illustrationData.alt}')"
                    />
                </picture>
            </div>
        `;
    },

    /**
     * Display the current page
     */
    displayCurrentPage() {
        // Use the stored active wrapper reference to find the correct page container
        if (!this.pagination.activeWrapper) {
            return;
        }

        const pageContainer = this.pagination.activeWrapper.querySelector('.pagination-page-container');
        if (!pageContainer || this.pagination.pages.length === 0) {
            return;
        }

        // Ensure current page is within bounds
        this.pagination.currentPage = Math.max(0, Math.min(this.pagination.currentPage, this.pagination.totalPages - 1));

        // Update page content instantly (no animation as per user preference)
        pageContainer.innerHTML = this.pagination.pages[this.pagination.currentPage];

        // Set fixed height to prevent layout shift
        pageContainer.style.height = `${this.pagination.containerHeight}px`;
        pageContainer.style.overflow = 'hidden';

        // Update progress indicator
        this.updatePaginationProgress();

        if (this.continuousReader?.active) {
            this.onContinuousPageDisplayed();
        } else {
            // Save page position
            this.savePagePosition();

            // Legacy chapter view is read-only while its route redirects to
            // the continuous reader. Keep this branch for direct old markup.
            if (window.authModule && this.currentBook && this.currentChapter !== null) {
            window.authModule.trackPageChange(
                this.currentBook.id,
                this.currentChapter,
                this.pagination.currentPage
            );

            // Mark chapter as complete if on last page
            const isLastPage = this.pagination.currentPage === this.pagination.totalPages - 1;
            if (isLastPage) {
                window.authModule.onChapterComplete(
                    this.currentBook.id,
                    this.currentChapter
                );
            }
        }
        }

        // Scroll to top of content area
        const chapterSection = this.continuousReader?.active
            ? document.getElementById('continuous-reader-section')
            : document.getElementById('chapter-detail-section');
        if (chapterSection) {
            const sectionTop = chapterSection.offsetTop;
            window.scrollTo({ top: sectionTop, behavior: 'instant' });
        }
    },

    /**
     * Setup navigation zones for tap/click navigation
     */
    setupNavigationZones(wrapperElement) {
        // Remove existing navigation zones
        const existingZones = wrapperElement.querySelectorAll('.pagination-nav-zone, .pagination-nav-button');
        existingZones.forEach(zone => zone.remove());

        // Navigation zones removed to enable text selection
        // Only create visible navigation buttons
        const prevButton = document.createElement('button');
        prevButton.className = 'pagination-nav-button pagination-nav-prev';
        prevButton.innerHTML = '‹';
        prevButton.setAttribute('aria-label', 'Previous page');
        prevButton.addEventListener('click', () => this.navigateToPreviousPage());

        const nextButton = document.createElement('button');
        nextButton.className = 'pagination-nav-button pagination-nav-next';
        nextButton.innerHTML = '›';
        nextButton.setAttribute('aria-label', 'Next page');
        nextButton.addEventListener('click', () => this.navigateToNextPage());

        // Add buttons to wrapper
        wrapperElement.appendChild(prevButton);
        wrapperElement.appendChild(nextButton);

        // Auto-hide timer for mobile/touch devices
        let buttonHideTimer = null;

        const showButtonsTemporarily = () => {
            wrapperElement.classList.add('buttons-visible');

            // Clear existing timer
            if (buttonHideTimer) {
                clearTimeout(buttonHideTimer);
            }

            // Hide after 1 second
            buttonHideTimer = setTimeout(() => {
                wrapperElement.classList.remove('buttons-visible');
            }, 1000);
        };

        // Show buttons on touch (mobile)
        wrapperElement.addEventListener('touchstart', (e) => {
            // Don't trigger if touching a button directly
            if (!e.target.classList.contains('pagination-nav-button')) {
                showButtonsTemporarily();
            }
        }, { passive: true });

        // Show buttons on click (fallback for devices without hover)
        wrapperElement.addEventListener('click', (e) => {
            // Only trigger on wrapper or content click, not button clicks
            if (!e.target.classList.contains('pagination-nav-button')) {
                showButtonsTemporarily();
            }
        });

        // Show buttons on hover (desktop) - also uses 5s auto-hide timer
        wrapperElement.addEventListener('mouseenter', (e) => {
            showButtonsTemporarily();
        });

        // Store timer reference for cleanup
        if (!this.pagination.buttonTimers) {
            this.pagination.buttonTimers = [];
        }
        this.pagination.buttonTimers.push(buttonHideTimer);

        // Update button visibility
        this.updateNavigationButtons();
    },

    /**
     * Setup touch gestures for mobile navigation
     */
    setupTouchGestures(wrapperElement) {
        wrapperElement.addEventListener('touchstart', (e) => {
            this.pagination.touchStartX = e.touches[0].clientX;
            this.pagination.touchStartY = e.touches[0].clientY;
        }, { passive: true });

        wrapperElement.addEventListener('touchend', (e) => {
            if (!this.pagination.touchStartX || !this.pagination.touchStartY) {
                return;
            }

            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;

            const deltaX = touchEndX - this.pagination.touchStartX;
            const deltaY = touchEndY - this.pagination.touchStartY;

            // Only trigger if horizontal swipe is more significant than vertical
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                if (deltaX > 0) {
                    // Swipe right - previous page
                    this.navigateToPreviousPage();
                } else {
                    // Swipe left - next page
                    this.navigateToNextPage();
                }
            }

            // Reset touch positions
            this.pagination.touchStartX = 0;
            this.pagination.touchStartY = 0;
        }, { passive: true });
    },

    /**
     * Navigate to previous page
     */
    navigateToPreviousPage() {
        if (this.pagination.isNavigating) {
            return;
        }

        // Check if we're at the first page of the current chapter
        if (this.pagination.currentPage <= 0) {
            if (this.continuousReader?.active) {
                this.navigateContinuousSegment(-1);
                return;
            }
            // Try to navigate to previous chapter (go to last page)
            this.navigateToPreviousChapter();
            return;
        }

        this.pagination.isNavigating = true;
        this.pagination.currentPage--;
        this.displayCurrentPage();

        setTimeout(() => {
            this.pagination.isNavigating = false;
        }, 100);
    },

    /**
     * Navigate to next page
     */
    navigateToNextPage() {
        if (this.pagination.isNavigating) {
            return;
        }

        // Check if we're at the last page of the current chapter
        if (this.pagination.currentPage >= this.pagination.totalPages - 1) {
            if (this.continuousReader?.active) {
                this.navigateContinuousSegment(1);
                return;
            }
            // Try to navigate to next chapter
            this.navigateToNextChapter();
            return;
        }

        this.pagination.isNavigating = true;
        this.pagination.currentPage++;
        this.displayCurrentPage();

        setTimeout(() => {
            this.pagination.isNavigating = false;
        }, 100);
    },

    /**
     * Navigate to next chapter (called when reaching end of current chapter)
     */
    navigateToNextChapter() {
        if (!this.currentBook || this.currentChapter === null || this.currentChapter === undefined) {
            return;
        }

        // Find the next chapter
        const nextChapter = this.chapters.find(ch => ch.chapter_number === this.currentChapter + 1);

        if (nextChapter) {
            // Set flag to prevent sticky header flicker during chapter transition
            this.isChapterBoundaryNavigation = true;

            // Navigate to next chapter's first page
            this.pagination.isNavigating = true;
            this.showChapterDetail(this.currentBook, nextChapter.chapter_number, false);

            // Update URL
            const newUrl = withBasePath(`/books/${this.currentBook.slug}/chapters/${nextChapter.chapter_number}`);
            window.history.pushState({
                type: 'chapter',
                bookId: this.currentBook.id,
                bookSlug: this.currentBook.slug,
                chapterNum: nextChapter.chapter_number
            }, '', newUrl);

            setTimeout(() => {
                this.pagination.isNavigating = false;
                this.isChapterBoundaryNavigation = false;
            }, 300);
        } else {
            // No next chapter - we're at the end of the book
            console.log('End of book reached');
        }
    },

    /**
     * Navigate to previous chapter (called when at beginning of current chapter)
     */
    navigateToPreviousChapter() {
        if (!this.currentBook || this.currentChapter === null || this.currentChapter === undefined) {
            return;
        }

        // Find the previous chapter
        const prevChapter = this.chapters.find(ch => ch.chapter_number === this.currentChapter - 1);

        if (prevChapter) {
            // Set flag to prevent sticky header flicker during chapter transition
            this.isChapterBoundaryNavigation = true;

            // Navigate to previous chapter - will go to last page after pagination loads
            this.pagination.isNavigating = true;
            this.pagination.shouldGoToLastPage = true; // Flag to indicate we should go to last page
            console.log('🔄 navigateToPreviousChapter: Set shouldGoToLastPage flag to true');
            this.showChapterDetail(this.currentBook, prevChapter.chapter_number, false);

            // Update URL
            const newUrl = withBasePath(`/books/${this.currentBook.slug}/chapters/${prevChapter.chapter_number}`);
            window.history.pushState({
                type: 'chapter',
                bookId: this.currentBook.id,
                bookSlug: this.currentBook.slug,
                chapterNum: prevChapter.chapter_number
            }, '', newUrl);

            setTimeout(() => {
                this.pagination.isNavigating = false;
                this.isChapterBoundaryNavigation = false;
            }, 300);
        } else {
            // No previous chapter - we're at the beginning of the book
            console.log('Beginning of book reached');
        }
    },

    /**
     * Update navigation button visibility
     */
    updateNavigationButtons() {
        const prevButton = document.querySelector('.pagination-nav-prev');
        const nextButton = document.querySelector('.pagination-nav-next');

        if (this.continuousReader?.active) {
            const descriptor = this.continuousReader.manifest.segments.find(item => item.id === this.continuousReader.currentSegmentId);
            const hasPrevious = this.pagination.currentPage > 0 || (descriptor && descriptor.ordinal > 0);
            const hasNext = this.pagination.currentPage < this.pagination.totalPages - 1 ||
                (descriptor && this.continuousReader.manifest.segments.some(item => item.mode === this.continuousReader.mode && item.ordinal === descriptor.ordinal + 1));
            if (prevButton) { prevButton.style.visibility = hasPrevious ? 'visible' : 'hidden'; prevButton.style.pointerEvents = hasPrevious ? 'auto' : 'none'; }
            if (nextButton) { nextButton.style.visibility = hasNext ? 'visible' : 'hidden'; nextButton.style.pointerEvents = hasNext ? 'auto' : 'none'; }
            return;
        }

        // Check if there are previous/next chapters (handles preface at chapter 0)
        const hasPrevChapter = this.chapters.some(ch => ch.chapter_number === this.currentChapter - 1);
        const hasNextChapter = this.chapters.some(ch => ch.chapter_number === this.currentChapter + 1);

        if (prevButton) {
            // Show prev button if not on first page OR if there's a previous chapter
            // Use visibility instead of display to preserve opacity-based auto-hide
            prevButton.style.visibility = (this.pagination.currentPage > 0 || hasPrevChapter) ? 'visible' : 'hidden';
            prevButton.style.pointerEvents = (this.pagination.currentPage > 0 || hasPrevChapter) ? 'auto' : 'none';
        }

        if (nextButton) {
            // Show next button if not on last page OR if there's a next chapter
            // Use visibility instead of display to preserve opacity-based auto-hide
            nextButton.style.visibility = (this.pagination.currentPage < this.pagination.totalPages - 1 || hasNextChapter) ? 'visible' : 'hidden';
            nextButton.style.pointerEvents = (this.pagination.currentPage < this.pagination.totalPages - 1 || hasNextChapter) ? 'auto' : 'none';
        }
    },

    /**
     * Update progress indicators with page numbers and percentage
     */
    updatePaginationProgress() {
        if (this.continuousReader?.active) {
            this.updateNavigationButtons();
            return;
        }
        const progressFill = document.getElementById('reading-progress-fill');
        const progressText = document.getElementById('reading-progress-text');

        if (!progressFill || !progressText) {
            return;
        }

        // Calculate percentage
        const percentage = this.pagination.totalPages > 0
            ? Math.round(((this.pagination.currentPage + 1) / this.pagination.totalPages) * 100)
            : 0;

        // Update progress bar
        progressFill.style.width = `${percentage}%`;

        // Update text with page numbers and percentage
        const pageText = `Page ${this.pagination.currentPage + 1} of ${this.pagination.totalPages} • ${percentage}%`;
        progressText.textContent = pageText;

        // Update navigation buttons
        this.updateNavigationButtons();
    },

    /**
     * Recalculate pagination when window resizes or settings change
     */
    recalculatePagination() {
        if (this.continuousReader?.active) {
            const marker = this.continuousReader.currentMarker;
            this.continuousReader.restoring = true;
            this.loadContinuousReaderAt(marker, marker?.chapter_id);
            return;
        }
        // Use the stored active wrapper reference
        if (!this.pagination.activeWrapper) {
            return;
        }

        const containerElement = this.pagination.activeWrapper.querySelector('.pagination-page-container');
        if (!containerElement) {
            return;
        }

        // Save current progress as percentage
        const progressPercentage = this.pagination.totalPages > 0
            ? this.pagination.currentPage / this.pagination.totalPages
            : 0;

        // Get ALL computed styles from current container (including inline fontSize!)
        const currentStyle = window.getComputedStyle(containerElement);

        // CRITICAL: Use original content from storage, NOT paginated content
        // The paginated content (this.pagination.pages) has been split across pages and lost structure
        // We need the original unpaginated content to recalculate properly
        let allContent;
        const viewMode = this.pagination.currentViewMode;

        // Determine which container ID to use based on view mode
        let containerIdToRestore;
        if (viewMode === 'side-by-side') {
            containerIdToRestore = 'chapter-side-by-side';
        } else if (viewMode === 'modern') {
            containerIdToRestore = 'chapter-modern-english';
        } else if (viewMode === 'summary') {
            containerIdToRestore = 'chapter-summary-text';
        } else {
            containerIdToRestore = 'chapter-fulltext';
        }

        console.log('[recalculatePagination] View mode:', viewMode, 'Container ID:', containerIdToRestore);

        // Try to get original content from storage
        if (this.pagination.originalContent && this.pagination.originalContent[containerIdToRestore]) {
            allContent = this.pagination.originalContent[containerIdToRestore];
            console.log('[recalculatePagination] Using original content from storage, length:', allContent.length);
        } else {
            // Fallback to joined pages (may lose structure for side-by-side)
            allContent = this.pagination.pages.join('');
            console.log('[recalculatePagination] WARNING: No original content found, using joined pages, length:', allContent.length);
        }

        console.log('[recalculatePagination] First 300 chars:', allContent.substring(0, 300));

        // Create temporary container with EXACT same styles
        const tempContainer = document.createElement('div');
        // CRITICAL: Copy the entire className to preserve classes like 'chapter-side-by-side'
        tempContainer.className = containerElement.className;
        console.log('[recalculatePagination] Temp container className:', tempContainer.className);

        // CRITICAL: Copy ALL styles that affect layout, especially fontSize
        tempContainer.style.fontSize = currentStyle.fontSize;
        tempContainer.style.fontFamily = currentStyle.fontFamily;
        tempContainer.style.lineHeight = currentStyle.lineHeight;
        tempContainer.style.padding = currentStyle.padding;
        tempContainer.style.boxSizing = currentStyle.boxSizing;

        tempContainer.innerHTML = allContent;
        console.log('[recalculatePagination] After setting innerHTML, checking structure...');
        const headers = tempContainer.querySelectorAll('.side-by-side-headers');
        const rows = tempContainer.querySelectorAll('.side-by-side-row');
        console.log('[recalculatePagination] Structure in temp container:', {
            headers: headers.length,
            rows: rows.length
        });

        containerElement.parentElement.appendChild(tempContainer);

        // Recalculate pages with correct styles
        this.calculatePages(tempContainer);

        // Restore approximate position
        this.pagination.currentPage = Math.floor(progressPercentage * this.pagination.totalPages);
        this.pagination.currentPage = Math.max(0, Math.min(this.pagination.currentPage, this.pagination.totalPages - 1));

        // Remove temporary container
        tempContainer.remove();

        // Display the new current page
        this.displayCurrentPage();
    },

    /**
     * Save current page position to localStorage
     */
    savePagePosition() {
        if (!this.currentBook || !this.currentChapter) {
            return;
        }

        const key = `pagination_${this.currentBook.id}_${this.currentChapter}`;
        localStorage.setItem(key, this.pagination.currentPage.toString());
    },

    /**
     * Load saved page position from localStorage
     */
    loadPagePosition() {
        if (!this.currentBook || !this.currentChapter) {
            return 0;
        }

        const key = `pagination_${this.currentBook.id}_${this.currentChapter}`;
        const savedPage = localStorage.getItem(key);
        return savedPage ? parseInt(savedPage, 10) : 0;
    },

    /**
     * Clear pagination (used when switching view modes or chapters)
     */
    clearPagination() {
        this.pagination.currentPage = 0;
        this.pagination.totalPages = 0;
        this.pagination.pages = [];
        this.pagination.containerHeight = 0;

        // Clear button auto-hide timers
        if (this.pagination.buttonTimers && this.pagination.buttonTimers.length > 0) {
            this.pagination.buttonTimers.forEach(timer => {
                if (timer) clearTimeout(timer);
            });
            this.pagination.buttonTimers = [];
        }

        // Clear stored original content when switching chapters
        // (but keep it when just switching view modes)
        // We'll handle this by only clearing on chapter navigation

        // Re-enable body/html scrolling
        document.documentElement.classList.remove('pagination-active');
        document.documentElement.style.overflow = '';
        document.body.classList.remove('pagination-active');
        document.body.style.overflow = '';
    },

    /**
     * Clear all pagination data including stored original content (for chapter navigation)
     */
    clearAllPaginationData() {
        this.clearPagination();
        this.pagination.originalContent = {};
    }

};
