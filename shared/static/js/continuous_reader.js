// Continuous reader: the paginated, segment-loading book reader with saved
// place, mode switching and progress. Cut verbatim from an app's reader.js;
// mode names, labels, widths and features come from window.READER_CONFIG via
// readerUtilsMixin. Merged onto the host app's prototype by platform.js, so
// every method still reads/writes `this.*` exactly as before.
//
// Host hooks: classifyUnit(text) -> block turns one unit's body into a block
// that blocksMixin.continuousReaderBlock (blocks.js) renders as
// {tag, className, content}; selectBook(book) is where the back button goes.
export const continuousReaderMixin = {
    async showContinuousReader(book, options = {}) {
        if (this.continuousReader?.active && this.currentBook?.id !== book.id) {
            await this.saveContinuousReader('navigation');
        }
        this.currentBook = book;
        this.currentView = 'reader';
        this.setupContinuousReaderExit();
        for (const id of ['reader-toc-button', 'reader-settings-button']) { const button = document.getElementById(id); if (button) button.disabled = true; }
        this.clearAllPaginationData();
        this.showOnlySections('continuous-reader-section');
        const status = document.getElementById('reader-status');
        const content = document.getElementById('continuous-reader-content');
        status?.classList.add('hidden');
        if (content) content.innerHTML = '';
        // Show a skeleton of the reading column only if the open is slow, so
        // cached opens don't flash it. Rendering the first segment replaces it.
        const skeletonTimer = setTimeout(() => {
            if (content && !content.childElementCount) content.innerHTML = this.readerSkeletonHtml();
        }, 250);
        const authReady = window.authModule?.initAuth?.();
        let manifest = null, authExpired = false;
        try {
            const manifestResponse = await fetch(`${this.apiBase}/reader/books/${book.id}/manifest`);
            authExpired = manifestResponse.status === 401 || manifestResponse.status === 403;
            const manifestData = await manifestResponse.json();
            if (manifestResponse.ok && manifestData.success) {
                manifest = manifestData.manifest;
                window.authModule?.cacheReaderManifest?.(manifest).catch(() => {});
            }
        } catch (_) { /* use the durable segment cache below */ }
        if (!authExpired) manifest ||= await Promise.resolve(window.authModule?.getCachedReaderManifest?.(book.id)).catch(() => null);
        if (!manifest) {
            clearTimeout(skeletonTimer);
            if (content) content.innerHTML = '';
            this.setContinuousReaderStatus(authExpired ? 'Please sign in again to open this book.' : 'Unable to open this book. Check your connection and try again.',
                authExpired ? () => location.reload() : () => this.showContinuousReader(book, options), authExpired ? 'Reload and sign in' : 'Retry');
            return;
        }
        await authReady;
        const state = await window.authModule?.getReaderState?.(book.id) || { book: null, modes: [] };
        const available = this.readerAvailableModes(manifest);
        const requestedMode = options.mode;
        const savedMode = state.book?.last_mode;
        const mode = available.includes(requestedMode) ? requestedMode :
            (available.includes(savedMode) ? savedMode : (this.readerConfig().default_modes.find(id => available.includes(id)) || available[0]));
        if (!mode) {
            clearTimeout(skeletonTimer);
            if (content) content.innerHTML = '';
            this.setContinuousReaderStatus('No readable content is available for this book.');
            return;
        }
        const modeState = state.modes?.find(item => item.mode === mode);
        let restoredMarker = options.restart ? null : modeState?.current_marker || null;
        if (restoredMarker && restoredMarker.content_version !== manifest.content_version) {
            const recovered = await this.recoverContinuousMarker(restoredMarker, mode);
            if (recovered) {
                restoredMarker = recovered;
                if (recovered.recovery_level === 'chapter_opening' || recovered.recovery_level === 'book_opening') {
                    this.setContinuousReaderStatus('This book changed; your place was restored approximately.');
                }
            }
        }
        const chapterId = this.resolveReaderChapter(manifest, options.chapter, options.legacyChapterNumber);
        // An explicit chapter destination wins over the saved place, unless
        // the saved place is already inside that chapter.
        if (chapterId && restoredMarker && Number(restoredMarker.chapter_id) !== Number(chapterId)) {
            restoredMarker = null;
        }
        this.continuousReader = {
            active: true, restoring: true, manifest, mode, state, modeState,
            currentMarker: restoredMarker,
            furthestMarker: modeState?.furthest_marker || null,
            segmentIds: [], currentSegmentId: null, chapterId,
            forwardTurn: false, pageTurnAt: Date.now(), terminalTimer: null,
        };
        this.setupContinuousReaderChrome();
        this.setupContinuousReaderLifecycle();
        await this.loadContinuousReaderAt(this.continuousReader.currentMarker, chapterId);
        clearTimeout(skeletonTimer);
        content?.querySelector('.reader-skeleton')?.remove();
    },

    readerSkeletonHtml() {
        const widths = [100, 96, 98, 72, 0, 100, 94, 97, 99, 60, 0, 100, 95, 88];
        const lines = widths.map(w => w ? `<span class="reader-skeleton-line" style="width:${w}%"></span>` : '<span class="reader-skeleton-gap"></span>').join('');
        return `<div class="reader-skeleton" role="status" aria-label="Opening book…"><span class="reader-skeleton-title"></span>${lines}</div>`;
    },

    resolveReaderChapter(manifest, rawChapter, legacyNumber = false) {
        if (!rawChapter) return null;
        const chapter = manifest.structure.find(entry => entry.kind === 'chapter' &&
            (legacyNumber ? String(entry.chapter_number) === String(rawChapter) : String(entry.chapter_id) === String(rawChapter)));
        return chapter?.chapter_id || null;
    },

    isContinuousReaderModeAvailable(mode) {
        const m = this.readerMode(mode);
        return !m?.min_width || window.matchMedia(`(min-width: ${m.min_width}px)`).matches;
    },

    async switchContinuousReaderMode(nextMode) {
        const reader = this.continuousReader;
        if (!reader?.active || nextMode === reader.mode || !this.isContinuousReaderModeAvailable(nextMode)) return;
        clearTimeout(reader.settleTimer);
        clearTimeout(reader.terminalTimer);
        const previousMode = reader.mode;
        const previousMarker = reader.currentMarker;
        await this.saveContinuousReader('mode_exit');
        reader.mode = nextMode;
        reader.restoring = true;
        reader.requests = new Map();
        reader.modeState = reader.state?.modes?.find(item => item.mode === nextMode) || null;
        reader.furthestMarker = reader.modeState?.furthest_marker || null;
        let destination = reader.modeState?.current_marker || null;
        if (!destination && previousMarker) {
            destination = await this.mapContinuousMarker(previousMarker, previousMode, nextMode);
        }
        reader.currentMarker = destination;
        reader.forwardTurn = false;
        await this.loadContinuousReaderAt(destination, destination?.chapter_id || previousMarker?.chapter_id);
    },

    async enforceContinuousReaderViewport() {
        const reader = this.continuousReader;
        const wideMode = reader?.active ? this.readerMode(reader.mode) : null;
        if (!reader?.active || !wideMode?.min_width || this.isContinuousReaderModeAvailable(reader.mode)) {
            if (reader?.active) this.setupContinuousReaderChrome();
            return;
        }
        const fallbacks = wideMode.narrow_fallback;
        const fallback = fallbacks.find(id => reader.manifest.modes.some(item => item.mode === id && item.availability !== 'unavailable')) || fallbacks[fallbacks.length - 1];
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
        if (reader.mode === wideMode.id) return;
        this.setContinuousReaderStatus(`${wideMode.label} is available on screens ${wideMode.min_width}px wide or larger.`);
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
        // Fetch the current and next segments in parallel, not back to back.
        const nextDescriptor = descriptors.find(item => item.ordinal === descriptor.ordinal + 1);
        const [loaded, next] = await Promise.all([
            this.fetchContinuousSegment(descriptor.id),
            nextDescriptor ? this.fetchContinuousSegment(nextDescriptor.id, true) : null,
        ]);
        if (!reader.active || this.continuousReader !== reader) return;
        if (!loaded) {
            this.setContinuousReaderStatus('This section needs a connection.', () => this.loadContinuousReaderAt(marker, chapterId));
            return;
        }
        document.getElementById('reader-status')?.classList.add('hidden');
        // Pages are cut by measuring text, so the reading font must be loaded
        // first. A web font (Figtree) arriving later re-wraps the text and
        // pushes each page's last line under the footer.
        const content = document.getElementById('continuous-reader-content');
        if (content && document.fonts?.load) {
            const style = getComputedStyle(content);
            await document.fonts.load(`${style.fontSize} ${style.fontFamily}`).catch(() => {});
        }
        if (!reader.active || this.continuousReader !== reader) return;
        reader.currentSegmentId = descriptor.id;
        reader.segmentIds = [loaded.id, next?.id].filter(Boolean);
        this.renderContinuousSegments([loaded, next].filter(Boolean), marker, chapterId);
    },

    async findContinuousSegmentForChapter(descriptors, chapterId) {
        // Manifests list each segment's chapters; a manifest cached before
        // that field existed falls back to scanning segments in order.
        if (descriptors.every(descriptor => Array.isArray(descriptor.chapter_ids))) {
            return descriptors.find(descriptor => descriptor.chapter_ids.some(id => Number(id) === Number(chapterId))) || null;
        }
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
        const request = fetch(`${this.apiBase}/reader/books/${this.currentBook.id}/segments/${encodeURIComponent(segmentId)}?mode=${reader.mode}&v=${encodeURIComponent(reader.manifest.content_version)}`)
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
                return cachedPromise.catch(() => null).then(cached => {
                    if (cached) return cached;
                    if (!prefetch) this.setContinuousReaderStatus('The next section needs a connection.');
                    return null;
                });
            });
        request.then(segment => { if (!segment) reader.requests.delete(segmentId); }, () => reader.requests.delete(segmentId));
        reader.requests.set(segmentId, request);
        return request;
    },

    // WebP + JPG URLs for a stored chapter illustration path
    // ("illustrations/1/2.jpg" or "/static/illustrations/1/2.png").
    illustrationSources(url) {
        let illustrationUrl = url;
        if (!illustrationUrl.startsWith('http')) {
            if (!illustrationUrl.startsWith('/static/')) {
                illustrationUrl = `/static/${illustrationUrl}`;
            }
            illustrationUrl = withBasePath(illustrationUrl);
        }
        const baseUrl = illustrationUrl.replace(/\.(png|jpg|jpeg)$/i, '');
        return { baseUrl, webpUrl: `${baseUrl}.webp`, jpgUrl: `${baseUrl}.jpg` };
    },

    // Chapter illustration shown under the chapter heading. A fixed-height
    // figure (see .reader-illustration) so pagination can measure it before
    // the image loads.
    continuousIllustrationHtml(chapterId, title) {
        if (!this.readerConfig().features.illustrations) return '';
        const entry = this.continuousReader.manifest?.structure?.find(item =>
            Number(item.chapter_id) === Number(chapterId) && item.illustration_url);
        if (!entry) return '';
        const { baseUrl, webpUrl, jpgUrl } = this.illustrationSources(entry.illustration_url);
        const alt = this.escapeHtml(`Illustration for ${title}`);
        return `<figure class="reader-illustration" data-reader-chapter="${Number(chapterId)}">
            <picture>
                <source srcset="${this.escapeHtml(webpUrl)}" type="image/webp">
                <img src="${this.escapeHtml(jpgUrl)}" alt="${alt}" onclick="window.summraApp?.openLightbox?.('${this.escapeHtml(baseUrl)}', '${alt}')">
            </picture>
        </figure>`;
    },

    renderContinuousSegments(segments, restoreMarker = null, chapterId = null) {
        const reader = this.continuousReader;
        const container = document.getElementById('continuous-reader-content');
        if (!reader?.active || !container) return;
        reader.unitsById = new Map();
        const modeConfig = this.readerMode(reader.mode);
        const sideBySide = this.readerLayout(reader.mode) === 'side_by_side';
        const html = [];
        let activeChapter = null;
        for (const segment of segments) {
            for (const unit of segment.units) {
                reader.unitsById.set(unit.id, unit);
                // Segment boundaries can fall mid-chapter, especially in verse.
                // Only the first logical unit owns the heading and illustration.
                if (unit.chapter_id !== activeChapter && unit.chapter_ordinal === 0) {
                    activeChapter = unit.chapter_id;
                    const title = unit.chapter_title || `Chapter ${unit.chapter_number || ''}`;
                    // Illustration below the heading; pagination keeps the
                    // heading on the same page as what follows it.
                    html.push(`<h2 class="reader-chapter-heading" data-reader-chapter="${unit.chapter_id}">${this.escapeHtml(title)}</h2>`);
                    html.push(this.continuousIllustrationHtml(unit.chapter_id, title));
                }
                if (sideBySide) {
                    const cell = (member, label) => {
                        if (!member?.available) return `<p class="reader-gap">${label} unavailable for this section.</p>`;
                        const block = this.continuousReaderBlock(member.content || '');
                        const className = block.className ? ` class="${block.className}"` : '';
                        return `<${block.tag}${className}>${block.content}</${block.tag}>`;
                    };
                    const cells = modeConfig.members.map(member =>
                        `<div class="side-by-side-cell ${member.cell_class}">${cell(unit.members[member.id], member.label)}</div>`).join('');
                    html.push(`<div class="side-by-side-row reader-alignment-row" data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="${unit.canonical_word_count || 0}">${cells}</div>`);
                } else if (unit.availability === 'gap') {
                    html.push(`<div class="reader-gap" data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="0">${modeConfig.label} unavailable for this section.</div>`);
                } else {
                    for (const block of this.continuousReaderBlocks(unit.content || '')) {
                        const className = block.className ? ` class="${block.className}"` : '';
                        const flow = block.flow ? ' data-reader-flow="true"' : '';
                        html.push(`<${block.tag}${className}${flow} data-reader-anchor="${unit.id}" data-reader-ordinal="${unit.ordinal}" data-reader-chapter="${unit.chapter_id}" data-reader-word-count="${unit.word_count || 0}">${block.content}</${block.tag}>`);
                    }
                }
            }
        }
        container.className = `continuous-reader-content ${sideBySide ? 'chapter-side-by-side' : ''}`;
        container.innerHTML = sideBySide
            ? `<div class="side-by-side-headers">${modeConfig.members.map(member => `<div class="side-by-side-header">${member.label}</div>`).join('')}</div>${html.join('')}`
            : html.join('');
        this.pagination.originalContent = {};
        this.initializePagination(container, sideBySide ? 'side-by-side' : reader.mode);
        const page = restoreMarker?.paragraph_id
            ? this.findContinuousPageForMarker(restoreMarker)
            : (chapterId ? this.findContinuousPageForChapter(chapterId) : -1);
        if (page >= 0) {
            this.pagination.currentPage = page;
            this.displayCurrentPage();
        }
        reader.restoring = false;
        // Opening/restoring never writes progress, but the chrome still needs
        // the marker that is visibly on screen for the next deliberate turn.
        this.settleContinuousReaderMarker();
    },

    // First page holding any of the chapter's content (its heading, when the
    // chapter starts inside the rendered segments).
    findContinuousPageForChapter(chapterId) {
        const selector = `[data-reader-chapter="${Number(chapterId)}"]`;
        return this.pagination.pages.findIndex(html => {
            const page = document.createElement('div');
            page.innerHTML = html;
            return !!page.querySelector(selector);
        });
    },

    // All visible fragments of a paragraph, measured consistently for saving
    // and restoring. Chinese uses character fractions: its whitespace word
    // count can be one even when the paragraph spans many pages. Keep the
    // existing word-based offsets for English and side-by-side mode switches.
    continuousParagraphPageSizes(paragraphId) {
        const reader = this.continuousReader;
        const fragments = [];
        for (let index = 0; index < this.pagination.pages.length; index += 1) {
            const page = document.createElement('div');
            page.innerHTML = this.pagination.pages[index];
            const anchors = [...page.querySelectorAll('[data-reader-anchor]')]
                .filter(candidate => candidate.dataset.readerAnchor === paragraphId);
            const flow = anchors.some(anchor => anchor.dataset.readerFlow === 'true');
            const text = anchors.map(candidate => this.readerLayout(reader.mode) === 'side_by_side'
                    ? (candidate.querySelector(`.side-by-side-cell.${this.readerMode(reader.mode).members[0].cell_class}`)?.textContent || candidate.textContent || '')
                    : candidate.textContent || '').join(' ');
            if (text) fragments.push({ index, text, flow });
        }
        const chinese = fragments.some(fragment => /\p{Script=Han}/u.test(fragment.text));
        const pages = fragments.map(({ index, text }) => ({index, size: chinese
            ? Array.from(text.replace(/\s/g, '')).length
            : text.trim().split(/\s+/).filter(Boolean).length}));
        const unit = reader?.unitsById?.get(paragraphId);
        const measured = pages.reduce((sum, page) => sum + page.size, 0);
        // Flattened tables repeat column labels for readability. Normalize the
        // displayed flow so every continuation has a restorable offset without
        // changing the underlying unit ID, content version or progress schema.
        const flow = fragments.some(fragment => fragment.flow);
        return { pages, total: chinese || flow ? measured : (unit?.word_count || unit?.canonical_word_count || measured) };
    },

    findContinuousPageForMarker(marker) {
        const { pages, total } = this.continuousParagraphPageSizes(marker.paragraph_id);
        const target = total * Math.max(0, Math.min(1, Number(marker.offset) || 0));
        let accumulated = 0;
        for (const [i, page] of pages.entries()) {
            if (!total || target < accumulated + page.size || i === pages.length - 1) return page.index;
            accumulated += page.size;
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
        const chapter = reader.manifest.structure.find(item => Number(item.chapter_id) === reader.currentMarker.chapter_id);
        document.getElementById('reader-chapter-title').textContent = chapter?.title || '';
        this.updateContinuousReaderProgress();
    },

    continuousMarkerOffset(anchor) {
        if (!anchor || !this.pagination?.pages?.length) return 0;
        const { pages, total } = this.continuousParagraphPageSizes(anchor.dataset.readerAnchor);
        if (!total) return 0;
        const prior = pages.filter(page => page.index < this.pagination.currentPage)
            .reduce((sum, page) => sum + page.size, 0);
        return Math.max(0, Math.min(0.99, prior / total));
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
        document.getElementById('reader-mode-settings')?.classList.toggle('hidden', this.readerAvailableModes(reader.manifest).length < 2);
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
        const wideMode = this.readerConfig().modes.find(mode => mode.min_width);
        const sideBySide = wideMode && reader.manifest.modes.find(item => item.mode === wideMode.id);
        const modeHelp = document.getElementById('reader-mode-help');
        if (modeHelp && wideMode) {
            modeHelp.textContent = sideBySide?.availability === 'unavailable'
                ? `${wideMode.label} is unavailable for this book.`
                : `${wideMode.label} is available on screens ${wideMode.min_width}px wide or larger.`;
        }
        this.setupContinuousReaderExit();
        for (const id of ['reader-toc-button', 'reader-settings-button']) document.getElementById(id).disabled = false;
        document.getElementById('reader-toc-button').onclick = () => this.toggleContinuousPanel('reader-toc-panel');
        document.getElementById('reader-settings-button').onclick = () => this.toggleContinuousPanel('reading-settings-panel');
        document.querySelectorAll('[data-reader-close]').forEach(button => button.onclick = () => this.closeContinuousPanel(button.dataset.readerClose));
        const settingsClose = document.getElementById('reading-settings-close');
        if (settingsClose) settingsClose.onclick = () => this.closeContinuousPanel('reading-settings-panel');
        const toc = document.getElementById('reader-toc-list');
        toc.innerHTML = reader.manifest.structure.map(entry => entry.kind === 'chapter'
            ? `<button type="button" data-reader-chapter-target="${entry.chapter_id}">${this.escapeHtml(entry.title)}</button>`
            : `<h3 class="reader-toc-part">${this.escapeHtml(entry.title)}</h3>`).join('');
        toc.querySelectorAll('[data-reader-chapter-target]').forEach(button => button.onclick = async () => {
            this.closeContinuousPanel('reader-toc-panel');
            reader.restoring = true;
            await this.loadContinuousReaderAt(null, button.dataset.readerChapterTarget);
            await this.saveContinuousReader('toc');
        });
    },

    // Release scrolling synchronously, before waiting for persistence or a
    // document navigation. Both SPA hosts and full-page hosts use this exit.
    leaveContinuousReader(cause = 'navigation') {
        const saving = this.saveContinuousReader(cause);
        const reader = this.continuousReader;
        if (reader) {
            reader.active = false;
            clearTimeout(reader.settleTimer);
            clearTimeout(reader.terminalTimer);
        }
        this.clearPagination();
        document.body.classList.remove('on-reader-page', 'on-chapter-page');
        document.getElementById('reading-settings-panel')?.classList.add('hidden');
        document.getElementById('reader-toc-panel')?.classList.add('hidden');
        document.getElementById('reader-toc-button')?.setAttribute('aria-expanded', 'false');
        return saving;
    },

    setupContinuousReaderLifecycle() {
        if (this.continuousReaderLifecycleBound) return;
        this.continuousReaderLifecycleBound = true;
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') this.saveContinuousReader('hidden');
        });
        window.addEventListener('pagehide', () => {
            // WebKit can retain the outgoing document's scroll lock through a
            // full navigation or its back/forward cache. Release it before the
            // browser snapshots the reader, just as we do for an in-app exit.
            this.continuousReaderSuspended = this.currentView === 'reader';
            this.leaveContinuousReader('pagehide');
        });
        window.addEventListener('pageshow', event => {
            if (!event.persisted || !this.continuousReaderSuspended || this.currentView !== 'reader') return;
            this.continuousReaderSuspended = false;
            const reader = this.continuousReader;
            if (!reader) return;
            reader.active = true;
            reader.restoring = true;
            document.body.classList.add('on-reader-page', 'on-chapter-page');
            this.loadContinuousReaderAt(reader.currentMarker, reader.currentMarker?.chapter_id);
        });
        const enforceViewport = () => this.enforceContinuousReaderViewport();
        window.addEventListener('resize', enforceViewport);
        this.readerConfig().modes.filter(mode => mode.min_width).forEach(mode =>
            window.matchMedia(`(max-width: ${mode.min_width - 1}px)`).addEventListener?.('change', enforceViewport));
        window.setInterval(() => {
            const reader = this.continuousReader;
            if (reader?.active && document.visibilityState === 'visible' && Date.now() - reader.pageTurnAt >= 15000) {
                this.saveContinuousReader('page_turn', 0, 15);
                reader.pageTurnAt = Date.now();
            }
        }, 15000);
    },

    setupContinuousReaderExit() {
        const button = document.getElementById('reader-back-button');
        if (!button) return;
        button.disabled = false;
        button.onclick = async () => {
            button.disabled = true;
            const saving = Promise.resolve(this.leaveContinuousReader()).catch(() => {});
            // keepalive persistence continues after navigation; a slow save
            // cannot hold the exit indefinitely.
            await Promise.race([saving, new Promise(resolve => setTimeout(resolve, 250))]);
            await this.selectBook(this.currentBook);
        };
    },

    continuousPanelOpen() {
        return ['reader-toc-panel', 'reading-settings-panel'].some(id => {
            const panel = document.getElementById(id);
            return panel && !panel.classList.contains('hidden');
        });
    },

    closeContinuousPanel(id) {
        document.getElementById(id)?.classList.add('hidden');
        const button = document.getElementById(id === 'reader-toc-panel' ? 'reader-toc-button' : 'reader-settings-button');
        button?.setAttribute('aria-expanded', 'false');
        button?.focus();
    },

    updateContinuousToc() {
        const current = this.continuousReader?.currentMarker?.chapter_id;
        (document.querySelectorAll?.('[data-reader-chapter-target]') || []).forEach(button => {
            if (Number(button.dataset.readerChapterTarget) === Number(current)) button.setAttribute('aria-current', 'location');
            else button.removeAttribute('aria-current');
        });
    },

    toggleContinuousPanel(id) {
        const panel = document.getElementById(id);
        if (!panel) return;
        if (!panel.classList.contains('hidden')) { this.closeContinuousPanel(id); return; }
        for (const other of ['reader-toc-panel', 'reading-settings-panel']) {
            if (other !== id) document.getElementById(other)?.classList.add('hidden');
        }
        panel.classList.remove('hidden');
        const opener = document.getElementById(id === 'reader-toc-panel' ? 'reader-toc-button' : 'reader-settings-button');
        opener?.setAttribute('aria-expanded', 'true');
        this.updateContinuousToc();
        const active = panel.querySelector('[aria-current="location"]');
        (active || panel.querySelector('button'))?.focus();
        active?.scrollIntoView({block:'nearest'});
        if (!this.readerPanelKeyboardBound) {
            this.readerPanelKeyboardBound = true;
            document.addEventListener('keydown', event => {
                const open = ['reader-toc-panel', 'reading-settings-panel'].map(key => document.getElementById(key)).find(el => el && !el.classList.contains('hidden'));
                if (!open) return;
                if (event.key === 'Escape') { event.preventDefault(); this.closeContinuousPanel(open.id); }
                if (event.key === 'Tab') {
                    const items = [...open.querySelectorAll('button:not([disabled]), a[href], input, select, [tabindex="0"]')].filter(el => el.getClientRects().length);
                    const first = items[0], last = items[items.length - 1];
                    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
                }
            });
        }
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

    async recoverContinuousMarker(marker, mode) {
        try {
            const response = await fetch(`${this.apiBase}/reader/books/${this.currentBook.id}/recover`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ marker: { ...marker, mode } }),
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
        // Sequential = arrived by turning forward one page (or into the next
        // section). Comparing paragraph ordinals missed nearly every turn: a
        // page holds several paragraphs, and long ones span pages.
        const sequential = reader.forwardTurn === true;
        reader.forwardTurn = false;
        const activeSeconds = document.visibilityState === 'visible'
            ? Math.min(60, Math.floor((Date.now() - reader.pageTurnAt) / 1000)) : 0;
        reader.pageTurnAt = Date.now();
        reader.currentMarker = marker;
        const chapter = reader.manifest.structure.find(item => Number(item.chapter_id) === marker.chapter_id);
        document.getElementById('reader-chapter-title').textContent = chapter?.title || '';
        this.updateContinuousReaderProgress();
        this.updateContinuousToc();
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
        const mode = reader.mode;
        const currentMarker = reader.currentMarker;
        const furthest = reader.furthestMarker;
        const qualified = boundaries > 0 && (!furthest || currentMarker.ordinal >= furthest.ordinal)
            ? currentMarker : null;
        if (qualified) reader.furthestMarker = qualified;
        let modeState = reader.state?.modes?.find(item => item.mode === mode);
        const saveStatus = document.getElementById('reader-save-status');
        if (saveStatus) saveStatus.textContent = 'Saving…';
        const mutation = await window.authModule?.queueReaderMutation?.({
            book_id: this.currentBook.id, mode, current_marker: currentMarker,
            qualified_furthest_marker: qualified, event_cause: cause,
            active_seconds_delta: activeSeconds, sequential_boundaries_delta: boundaries,
            base_revision: modeState?.revision ?? 0,
            ...extra,
        });
        if (saveStatus) saveStatus.textContent = mutation?.conflict ? 'Updated on another device' : mutation ? 'Saved' : 'Not saved — check connection';
        // Keep the in-memory (this tab only) projection in step with the save
        // just made, so switching modes mid-session reflects it immediately
        // instead of the marker fetched when the reader first opened. The
        // durable copy of this state lives only in the server DB.
        reader.state ||= { book: null, modes: [] };
        reader.state.modes ||= [];
        const projectionMode = mutation?.projection?.modes?.find(item => item.mode === mode);
        if (projectionMode) {
            modeState = projectionMode;
            const index = reader.state.modes.findIndex(item => item.mode === mode);
            if (index === -1) reader.state.modes.push(modeState); else reader.state.modes[index] = modeState;
        } else {
            if (!modeState) {
                modeState = { book_id: this.currentBook.id, mode };
                reader.state.modes.push(modeState);
            }
            modeState.current_marker = currentMarker;
            modeState.furthest_marker = qualified || furthest || modeState.furthest_marker || null;
        }
        if (mutation?.projection?.book) reader.state.book = mutation.projection.book;
        else if (reader.state.book) reader.state.book.last_mode = mode;
        if (reader.mode === mode) {
            reader.modeState = modeState;
            reader.furthestMarker = modeState.furthest_marker;
            this.updateContinuousReaderProgress();
        }
    },

    // Footer % and bar show where you are now (furthest is what's saved).
    updateContinuousReaderProgress() {
        const reader = this.continuousReader;
        const mode = reader?.manifest?.modes?.find(item => item.mode === reader.mode);
        const marker = reader?.currentMarker || reader?.furthestMarker;
        const wordPosition = this.continuousMarkerWordPosition(marker);
        const percentage = mode?.total_word_count && marker
            ? (reader.state?.book?.status === 'finished' && marker.paragraph_id === mode.terminal_paragraph_id ? 100 : Math.min(99, Math.max(0, Math.round(wordPosition * 100 / mode.total_word_count))))
            : 0;
        const text = document.getElementById('continuous-reader-progress');
        if (text) text.textContent = `${percentage}%`;
        const fill = document.getElementById('reader-progress-fill');
        if (fill) fill.style.width = `${percentage}%`;
    },

    setContinuousReaderStatus(message, retry = null, label = 'Retry') {
        const status = document.getElementById('reader-status');
        if (!status) return;
        status.textContent = message;
        if (retry) {
            const button = document.createElement('button');
            button.type = 'button'; button.textContent = label;
            button.onclick = () => { button.disabled = true; Promise.resolve(retry()).catch(() => { button.disabled = false; }); };
            status.appendChild(button);
        }
        status.classList.remove('hidden');
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
        if (direction > 0) reader.forwardTurn = true;
        this.renderContinuousSegments([loaded], null);
    },
};
