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

// Pagination state for chapter reading; a host sets this.pagination to it.
export function createPaginationState() {
    return {
        enabled: true, // Pagination is enabled by default
        currentPage: 0,
        totalPages: 0,
        pages: [], // Array of page content
        containerHeight: 0,
        isNavigating: false, // Prevent rapid page changes
        currentViewMode: 'original' // Track current view mode for pagination
    };
}

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

            // Space on a focused control should activate that control.
            if (e.key === ' ' && e.target.closest?.('button, a, select, summary')) {
                return;
            }

            const back = e.key === 'ArrowLeft' || e.key === 'PageUp' || (e.key === ' ' && e.shiftKey);
            const forward = e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey);
            if (back) {
                e.preventDefault();
                this.navigateToPreviousPage();
            } else if (forward) {
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

                // A sideways trackpad swipe counts like the wheel: swipe left
                // (deltaX > 0) = next page, like scrolling down.
                const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;

                // Debounce rapid scroll events
                clearTimeout(this.pagination.wheelTimeout);
                this.pagination.wheelTimeout = setTimeout(() => {
                    if (delta > 0) {
                        this.navigateToNextPage();
                    } else if (delta < 0) {
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

        this.showPageTurnHintOnce();

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
            ? (document.querySelector('.continuous-reader-chrome')?.offsetHeight || 59)
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
        // its HTML to every page below; each measuring page starts with it,
        // so the rows are measured with the banner's space already taken.
        let sxsHeadersHTML = '';
        if (containerElement.classList.contains('chapter-side-by-side')) {
            const headersEl = containerElement.querySelector('.side-by-side-headers');
            if (headersEl) {
                sxsHeadersHTML = headersEl.outerHTML;
            }
            // For side-by-side view: rows are the atomic blocks, plus the
            // full-width chapter heading and illustration.
            blocks = Array.from(containerElement.querySelectorAll('h2.reader-chapter-heading, .side-by-side-row, figure.reader-illustration'));
            console.log('[calculatePages] Side-by-side mode, found blocks:', blocks.length,
                        'headers pulled out:', !!sxsHeadersHTML);
        } else {
            // For regular views: use paragraphs and headings as blocks
            const extraBlocks = this.readerConfig().extra_page_blocks;
            blocks = Array.from(containerElement.querySelectorAll('p, h1, h2, h3, h4, h5, h6, blockquote, pre, ul, ol, figure.reader-illustration' + (extraBlocks ? `, ${extraBlocks}` : '')));
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
        // Computed line-height is in px; the live page inherits the unitless
        // ratio, which scales with each element's font size. Measuring with
        // px gave a 25.6px chapter heading a 28px line instead of 44.8px.
        const lineHeightPx = parseFloat(computedStyle.lineHeight);
        const fontSizePx = parseFloat(computedStyle.fontSize);
        const measuringLineHeight = lineHeightPx && fontSizePx
            ? String(lineHeightPx / fontSizePx) : computedStyle.lineHeight;

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
                line-height: ${measuringLineHeight};
                padding: ${computedStyle.padding};
                box-sizing: ${computedStyle.boxSizing};
            `;
            pageDiv.innerHTML = sxsHeadersHTML;
            // Measure beside the live page so reader CSS scoped to its
            // ancestors (row padding, borders) applies to the measurement.
            (containerElement.parentElement || document.body).appendChild(pageDiv);
            return pageDiv;
        };

        const pages = [];
        let blockIndex = 0;
        let safetyCounter = 0;

        // Incremental algorithm: Build one page at a time
        while (blockIndex < blocks.length) {
            safetyCounter++;
            // Safety: no more than 3x the number of blocks. Re-read each pass:
            // splitting a long paragraph or row adds its remainder to blocks.
            if (safetyCounter > blocks.length * 3) {
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
                // A chapter starts on a new page, as in a printed book. The
                // reading position is a page's first paragraph, so a page that
                // began with the previous chapter's end placed the reader (and
                // a mode switch) in the previous chapter.
                if (pageBlocks.length > 0 && block.matches?.('h2.reader-chapter-heading')) break;
                const clone = block.cloneNode(true);
                pageDiv.appendChild(clone);

                // Check for overflow using native scrollHeight (pixel-perfect!)
                if (pageDiv.scrollHeight > this.pagination.containerHeight) {
                    // Overflow detected - remove last block
                    pageDiv.removeChild(clone);

                    // Side-by-side rows split proportionally, also to fill the
                    // rest of a partly used page; otherwise move to the next page.
                    if (block.classList && block.classList.contains('side-by-side-row')) {
                        const splitResult = this.splitSideBySideRowToFit(
                            block, pageDiv, this.pagination.containerHeight, pageBlocks.length === 0);
                        if (splitResult.firstRow) {
                            pageDiv.appendChild(splitResult.firstRow);
                            pageBlocks.push(splitResult.firstRow.outerHTML);
                            blocks.splice(blockIndex + 1, 0, splitResult.remainderRow);
                            blockIndex++;
                            break;
                        }
                        if (pageBlocks.length === 0) {
                            // A single unit taller than the page: force it.
                            pageDiv.appendChild(clone);
                            pageBlocks.push(block.outerHTML);
                            blockIndex++;
                        }
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
            pageDiv.remove();
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
     * Where each unit of a text block starts: words, Han characters, or lines for verse
     * (.reader-verse, lines separated by <br>). Slicing between these points
     * with a Range keeps inline markup such as <em>.
     * Returns { starts: [{node, offset}], texts: [string] }.
     */
    textUnits(el) {
        const starts = [];
        let texts = [];
        if (el.classList.contains('reader-verse')) {
            starts.push({ node: el, offset: 0 });
            el.querySelectorAll('br').forEach(br => {
                const parent = br.parentNode;
                starts.push({ node: parent, offset: Array.prototype.indexOf.call(parent.childNodes, br) + 1 });
            });
            texts = starts.map((_, i) => this.sliceUnits(el, { starts }, i, i + 1, true));
        } else {
            const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                // Chinese has no spaces between words. Offer character boundaries
                // to the same splitter both apps use, retaining Latin words and
                // Unicode code points (including supplementary Han) intact.
                const tokens = /\p{Script=Han}\p{Mark}*|[^\s\p{Script=Han}]+/gu;
                for (const match of node.data.matchAll(tokens)) {
                    starts.push({ node, offset: match.index });
                    texts.push(match[0]);
                }
            }
        }
        return { starts, texts };
    },

    /** HTML (or text, with asText) of units [from, to) of a text block. */
    sliceUnits(el, units, from, to, asText = false) {
        const range = document.createRange();
        range.setStart(units.starts[from].node, units.starts[from].offset);
        if (to >= units.starts.length) range.setEnd(el, el.childNodes.length);
        else range.setEnd(units.starts[to].node, units.starts[to].offset);
        if (asText) return range.toString().trim();
        const div = document.createElement('div');
        let fragment = range.cloneContents();
        // cloneContents excludes its common ancestor. When both cut points
        // are inside one <em>/<strong>, restore that inline ancestor chain
        // so the page fragment keeps the original emphasis.
        let ancestor = range.commonAncestorContainer;
        if (ancestor.nodeType !== Node.ELEMENT_NODE) ancestor = ancestor.parentNode;
        while (ancestor && ancestor !== el) {
            const wrapper = ancestor.cloneNode(false);
            wrapper.appendChild(fragment);
            fragment = wrapper;
            ancestor = ancestor.parentNode;
        }
        div.appendChild(fragment);
        // A verse slice ends with the line break before the next line.
        while (div.lastChild && (div.lastChild.nodeName === 'BR'
            || (div.lastChild.nodeType === Node.TEXT_NODE && !div.lastChild.data.trim()))) {
            div.lastChild.remove();
        }
        return div.innerHTML.trim();
    },

    /**
     * Split paragraph to fit remaining space using binary search (O(log n)),
     * at a word/Han-character boundary (a line boundary for verse).
     * Returns {firstPart: Element, remainder: String} or {firstPart: null}
     */
    splitParagraphToFit(paragraph, pageDiv, pageHeight) {
        const units = this.textUnits(paragraph);
        const count = units.starts.length;
        if (count <= 1) {
            return { firstPart: null, remainder: null };
        }
        const makePart = (to) => {
            const part = paragraph.cloneNode(false);
            part.innerHTML = this.sliceUnits(paragraph, units, 0, to);
            return part;
        };

        // Binary search for maximum units that fit
        let left = 1;
        let right = count - 1;
        let bestFit = 0;
        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const testP = makePart(mid);
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
        return { firstPart: makePart(bestFit), remainder: this.sliceUnits(paragraph, units, bestFit, count) };
    },

    /**
     * Split a side-by-side row so its first part fills the remaining space.
     * Each column is filled independently as far as it fits (a row is as
     * tall as its taller cell), then continues on the next page; a column
     * whose text runs out leaves its later cells empty. On a partly used
     * page, a split leaving under three lines is refused.
     * Returns {firstRow, remainderRow} or {firstRow: null}.
     */
    splitSideBySideRowToFit(row, pageDiv, pageHeight, pageIsEmpty = true) {
        const members = this.readerConfig().modes.find(mode => mode.layout === 'side_by_side')?.members;
        const cellClasses = members?.length ? members.map(member => member.cell_class) : ['original', 'modern'];
        const sides = cellClasses.map(cellClass => `.side-by-side-cell.${cellClass}`).map(selector => {
            const el = row.querySelector(selector)?.firstElementChild;
            return el ? { selector, el, units: this.textUnits(el) } : null;
        });
        if (sides.some(side => !side)) return { firstRow: null };
        const counts = sides.map(side => side.units.starts.length);

        const buildRow = (cuts, remainder) => {
            const clone = row.cloneNode(true);
            sides.forEach((side, i) => {
                const target = clone.querySelector(side.selector).firstElementChild;
                const [from, to] = remainder ? [cuts[i], counts[i]] : [0, cuts[i]];
                target.innerHTML = from < to ? this.sliceUnits(side.el, side.units, from, to) : '';
                if (remainder && cuts[i] > 0) target.classList.add('paragraph-continuation');
            });
            return clone;
        };
        const measure = cuts => {
            const testRow = buildRow(cuts, false);
            pageDiv.appendChild(testRow);
            const result = { fits: pageDiv.scrollHeight <= pageHeight, height: testRow.offsetHeight };
            pageDiv.removeChild(testRow);
            return result;
        };

        // Largest prefix of one column that fits with the other column empty.
        const fill = i => {
            let low = 1;
            let high = counts[i];
            let best = 0;
            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                if (measure(counts.map((_, j) => (j === i ? mid : 0))).fits) {
                    best = mid;
                    low = mid + 1;
                } else {
                    high = mid - 1;
                }
            }
            return best;
        };
        const cuts = [fill(0), fill(1)];
        if (cuts.every(cut => cut === 0) || cuts.every((cut, i) => cut === counts[i])) return { firstRow: null };
        if (!pageIsEmpty) {
            const lineHeight = parseFloat(getComputedStyle(sides[0].el).lineHeight) || 24;
            if (measure(cuts).height < lineHeight * 3) return { firstRow: null };
        }
        return { firstRow: buildRow(cuts, false), remainderRow: buildRow(cuts, true) };
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

        // Mouse: these are the margin click strips. Touch: visually hidden
        // (swipe turns pages) and kept for screen readers. See style.css.
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

        // Update button visibility
        this.updateNavigationButtons();
    },

    /**
     * Setup touch gestures for mobile navigation
     */
    setupTouchGestures(wrapperElement) {
        // Like Kindle: the page follows the finger with the neighboring page
        // already rendered one screen width beside it, and both slide edge to
        // edge. On release it turns (a long drag or a quick flick) or snaps
        // back. Where there is no page to turn to, the drag meets resistance.
        let drag = null;
        let neighbor = null; // { el, side: 1 next | -1 previous, filled }
        let cleanupTimer = null;
        const pageEl = () => wrapperElement.querySelector('.pagination-page-container:not(.pagination-neighbor)');
        const stride = () => window.innerWidth;
        const slide = (x, ms) => {
            [pageEl(), neighbor?.el].forEach(el => {
                if (!el) return;
                el.style.transition = ms ? `transform ${ms}ms ease-out` : 'none';
                el.style.transform = x ? `translateX(${x}px)` : '';
            });
        };
        const removeNeighbor = () => {
            neighbor?.el.remove();
            neighbor = null;
            wrapperElement.classList.remove('is-swiping');
        };
        // A copy of the page element (same classes, font and size styles, so
        // it renders identically) holding the next or previous page. Anchors
        // and ids are stripped so marker and progress logic never see it.
        const showNeighbor = (side) => {
            if (neighbor?.side === side) return;
            removeNeighbor();
            const page = pageEl();
            if (!page) return;
            const el = page.cloneNode(false);
            el.classList.add('pagination-neighbor');
            el.removeAttribute('id');
            el.setAttribute('aria-hidden', 'true');
            el.inert = true;
            const html = this.pagination.pages[this.pagination.currentPage + side];
            el.innerHTML = html || '';
            el.querySelectorAll('[data-reader-anchor]').forEach(node => node.removeAttribute('data-reader-anchor'));
            el.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
            el.style.top = `${page.offsetTop}px`;
            el.style.left = `${side * stride()}px`;
            el.style.width = `${page.offsetWidth}px`;
            wrapperElement.appendChild(el);
            wrapperElement.classList.add('is-swiping');
            neighbor = { el, side, filled: Boolean(html) };
        };

        wrapperElement.addEventListener('touchstart', (e) => {
            const selection = window.getSelection();
            if (e.touches.length !== 1 || this.pagination.isNavigating || (selection && !selection.isCollapsed)) {
                drag = null;
                return;
            }
            clearTimeout(cleanupTimer);
            drag = { x: e.touches[0].clientX, y: e.touches[0].clientY, t: e.timeStamp, axis: null };
        }, { passive: true });

        wrapperElement.addEventListener('touchmove', (e) => {
            if (!drag || e.touches.length !== 1) return;
            const dx = e.touches[0].clientX - drag.x;
            const dy = e.touches[0].clientY - drag.y;
            if (!drag.axis && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
                drag.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
            }
            if (drag.axis !== 'x') return;
            const { hasPrevious, hasNext } = this.pageTurnAvailability();
            const side = dx > 0 ? -1 : 1;
            const blocked = side < 0 ? !hasPrevious : !hasNext;
            if (blocked) removeNeighbor();
            else showNeighbor(side);
            slide(blocked ? dx / 3 : dx, 0);
        }, { passive: true });

        // Hidden (offsetParent null) once the reader is left, e.g. when the
        // drag was iOS's edge-swipe back gesture.
        const onScreen = () => wrapperElement.isConnected && wrapperElement.offsetParent !== null;
        const release = (e) => {
            const current = drag;
            drag = null;
            if (!current || current.axis !== 'x') return;
            if (!onScreen()) {
                slide(0, 0);
                removeNeighbor();
                return;
            }
            const dx = e.changedTouches[0].clientX - current.x;
            const elapsed = Math.max(1, e.timeStamp - current.t);
            const width = wrapperElement.clientWidth;
            const flick = Math.abs(dx) > 30 && Math.abs(dx) / elapsed > 0.5;
            const forward = dx < 0;
            const { hasPrevious, hasNext } = this.pageTurnAvailability();
            const canTurn = forward ? hasNext : hasPrevious;
            if (e.type === 'touchend' && canTurn && (Math.abs(dx) > width * 0.25 || flick)) {
                const distance = stride();
                const ms = Math.max(120, Math.round(300 * (1 - Math.abs(dx) / distance)));
                slide(forward ? -distance : distance, ms);
                cleanupTimer = setTimeout(() => {
                    if (!onScreen()) {
                        slide(0, 0);
                        removeNeighbor();
                        return;
                    }
                    const rendered = neighbor?.filled;
                    if (forward) this.navigateToNextPage();
                    else this.navigateToPreviousPage();
                    // The neighbor was a rendered page: the real page now shows
                    // it, so put things back in the same frame (no flash).
                    // Otherwise the next section loads and rebuilds the reader;
                    // keep the page out of view until then.
                    if (rendered) {
                        slide(0, 0);
                        removeNeighbor();
                    } else {
                        cleanupTimer = setTimeout(() => { slide(0, 0); removeNeighbor(); }, 3000);
                    }
                }, ms);
            } else {
                slide(0, 200);
                cleanupTimer = setTimeout(removeNeighbor, 200);
            }
        };
        wrapperElement.addEventListener('touchend', release, { passive: true });
        wrapperElement.addEventListener('touchcancel', release, { passive: true });
    },

    /**
     * First time only: tell a mouse reader about the margins, wheel and keys,
     * or show a touch reader that the page swipes (label plus a nudge).
     */
    async showPageTurnHintOnce() {
        if (!this.readerConfig().features.page_turn_hint) return;
        if (this.pagination.hintShown) return;
        this.pagination.hintShown = true;
        await window.authModule?.initAuth?.();
        // The wrapper may have been rebuilt (resize, font change) meanwhile.
        const wrapperElement = this.pagination.activeWrapper;
        const mouse = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
        const key = mouse ? 'reader_nav_desktop' : 'reader_swipe_mobile';
        if (!window.authModule || window.authModule.hintSeen(key) || !wrapperElement?.isConnected) return;
        window.authModule.markHintSeen(key);

        const hint = document.createElement('div');
        hint.className = 'page-turn-hint';
        hint.setAttribute('role', 'status');
        hint.textContent = mouse
            ? 'Click the margins, scroll, or use ← → to turn pages'
            : 'Swipe to turn pages';
        // Attach to the reader section, which outlives a wrapper rebuild (the
        // reader re-paginates shortly after opening). CSS nudges the page
        // inside it.
        const section = wrapperElement.closest('section') || document.body;
        section.appendChild(hint);
        if (!mouse) section.classList.add('hint-nudge');

        const events = ['touchstart', 'mousedown', 'wheel', 'keydown'];
        const dismiss = () => {
            clearTimeout(timer);
            events.forEach(type => document.removeEventListener(type, dismiss, true));
            section.classList.remove('hint-nudge');
            hint.classList.add('page-turn-hint-out');
            setTimeout(() => hint.remove(), 300);
        };
        const timer = setTimeout(dismiss, 6000);
        events.forEach(type => document.addEventListener(type, dismiss, { capture: true, passive: true }));
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
        // A one-page forward turn is what counts as sequential reading.
        if (this.continuousReader?.active) this.continuousReader.forwardTurn = true;
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

        const { hasPrevious, hasNext } = this.pageTurnAvailability();
        if (prevButton) {
            prevButton.style.visibility = hasPrevious ? 'visible' : 'hidden';
            prevButton.style.pointerEvents = hasPrevious ? 'auto' : 'none';
        }
        if (nextButton) {
            nextButton.style.visibility = hasNext ? 'visible' : 'hidden';
            nextButton.style.pointerEvents = hasNext ? 'auto' : 'none';
        }
    },

    /**
     * Whether there is a page (or a chapter/segment) before and after this one.
     */
    pageTurnAvailability() {
        const notFirstPage = this.pagination.currentPage > 0;
        const notLastPage = this.pagination.currentPage < this.pagination.totalPages - 1;
        if (this.continuousReader?.active) {
            const descriptor = this.continuousReader.manifest.segments.find(item => item.id === this.continuousReader.currentSegmentId);
            return {
                hasPrevious: notFirstPage || Boolean(descriptor && descriptor.ordinal > 0),
                hasNext: notLastPage || Boolean(descriptor && this.continuousReader.manifest.segments.some(item => item.mode === this.continuousReader.mode && item.ordinal === descriptor.ordinal + 1)),
            };
        }
        // Previous/next chapters (handles preface at chapter 0)
        return {
            hasPrevious: notFirstPage || this.chapters.some(ch => ch.chapter_number === this.currentChapter - 1),
            hasNext: notLastPage || this.chapters.some(ch => ch.chapter_number === this.currentChapter + 1),
        };
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
