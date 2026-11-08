// Distill Listen: plays pre-rendered chapter audio in step with the reader.
// One <audio> element; position is kept in localStorage (survives an iOS app
// kill) and saved to the server as the summary mode's reading position.

const RATES = [1, 1.25, 1.5, 1.75, 2];
const LOCAL_EVERY_MS = 5000;
const SERVER_EVERY_MS = 30000;

// The unit playing at `ms`, and how far through it (0..1). A gap belongs to the unit before it.
export function unitAt(timings, ms) {
    let index = 0;
    for (let i = 0; i < timings.length; i += 1) {
        if (timings[i].start_ms <= ms) index = i; else break;
    }
    const unit = timings[index];
    const span = Math.max(1, unit.end_ms - unit.start_ms);
    return { index, paragraph_id: unit.paragraph_id, offset: Math.max(0, Math.min(1, (ms - unit.start_ms) / span)) };
}

// Where in the chapter audio a unit (at an offset through it) starts. Unknown units start at 0.
export function msFor(timings, paragraphId, offset = 0) {
    const unit = timings.find(item => item.paragraph_id === paragraphId);
    if (!unit) return 0;
    return Math.round(unit.start_ms + (unit.end_ms - unit.start_ms) * Math.max(0, Math.min(1, offset)));
}

// The timed unit at or before a reader unit id (tables and images have no audio of their own).
function nearestUnit(timings, paragraphId) {
    const [chapter, block] = String(paragraphId).split('.').map(Number);
    let best = timings[0];
    for (const item of timings) {
        const [c, b] = item.paragraph_id.split('.').map(Number);
        if (c === chapter && b <= block) best = item;
    }
    return best;
}

const clock = ms => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;

export class Listener {
    constructor(reader, book) {
        this.reader = reader;
        this.book = book;
        this.chapters = [];
        this.index = -1;
        this.audio = null;
        this.unit = null;
        this.following = true;
        this.navigating = false;
        this.lastLocal = 0;
        this.lastServer = 0;
        this.startedAt = null;
        this.dirty = false;        // the audio moved since the last server save
        this.pendingStart = null;  // seconds to seek to once the audio's metadata loads
        this.failed = false;
        this.key = `distill-listen-${book.id}`;
    }

    get timings() { return this.chapters[this.index]?.timings || []; }

    $(id) { return document.getElementById(id); }

    async init() {
        try {
            const response = await fetch(withBasePath(`/api/books/${this.book.slug}/audio`), { credentials: 'include' });
            const data = response.ok && (response.headers.get('content-type') || '').includes('json') ? await response.json() : null;
            this.chapters = data?.chapters || [];
        } catch (_) { this.chapters = []; }
        if (!this.chapters.length) return false;
        // Inside the reader footer, so pages are cut above the player, never under it.
        document.querySelector('.continuous-reader-footer')?.prepend(this.$('listen-bar'));
        this.addButton();
        this.bindBar();
        this.watchManualPaging();
        const saved = this.saved();
        if (saved) this.showResume(saved);
        return true;
    }

    addButton() {
        const toolbar = document.querySelector('.reader-toolbar-right');
        if (!toolbar || this.$('listen-button')) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.id = 'listen-button';
        button.className = 'reader-toolbar-btn reader-icon-btn';
        button.title = 'Listen';
        button.setAttribute('aria-label', 'Listen');
        button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="6" rx="1"/><rect x="17" y="14" width="4" height="6" rx="1"/></svg>';
        button.addEventListener('click', () => this.listenFromReadingPosition());
        toolbar.prepend(button);
    }

    bindBar() {
        this.$('listen-play').addEventListener('click', () => (this.audio && !this.audio.paused ? this.pause() : this.resume()));
        this.$('listen-back').addEventListener('click', () => this.seekBy(-15));
        this.$('listen-fwd').addEventListener('click', () => this.seekBy(30));
        this.$('listen-next').addEventListener('click', () => this.nextChapter());
        this.$('listen-rate').addEventListener('click', () => this.setRate(RATES[(RATES.indexOf(this.rate()) + 1) % RATES.length]));
        this.$('listen-follow').addEventListener('click', () => { this.following = true; this.$('listen-follow').hidden = true; this.follow(true); });
        this.$('listen-resume').addEventListener('click', () => this.resumeSaved());
        this.$('listen-reload').addEventListener('click', () => location.reload());
        this.$('listen-close').addEventListener('click', () => { this.pause(); this.showBar(false); });
        window.addEventListener('pagehide', () => this.saveAll());
        document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.saveAll(); });
    }

    // Paging away from the spoken paragraph while audio plays stops the text
    // following the audio. A re-layout that keeps it on screen does not count.
    watchManualPaging() {
        const original = this.reader.onContinuousPageDisplayed.bind(this.reader);
        this.reader.onContinuousPageDisplayed = () => {
            original();
            const page = document.querySelector('#continuous-reader-content .pagination-page-container') || document;
            const spokenVisible = !!this.unit && !!page.querySelector(`[data-reader-anchor="${this.unit}"]`);
            if (!this.navigating && this.unit && !spokenVisible && this.audio && !this.audio.paused && this.following) {
                this.following = false;
                this.$('listen-follow').hidden = false;
            }
            this.highlight();
        };
    }

    showBar(visible) {
        const bar = this.$('listen-bar');
        if (bar.hidden !== visible) return;
        bar.hidden = !visible;
        window.dispatchEvent(new Event('resize'));  // the reader re-cuts its pages
    }

    rate() { return this.audio?.playbackRate || this.saved()?.rate || 1; }

    saved() {
        try { return JSON.parse(localStorage.getItem(this.key) || 'null'); } catch (_) { return null; }
    }

    showResume(saved) {
        const chapter = this.chapters.find(item => item.chapter_id === saved.chapter_id);
        if (!chapter) return;
        this.showBar(true);
        const resume = this.$('listen-resume');
        resume.textContent = `Resume listening · ${chapter.title}, ${clock(saved.ms)}`;
        resume.hidden = false;
        this.$('listen-title').textContent = chapter.title;
    }

    ensureAudio() {
        if (this.audio) return this.audio;
        const audio = new Audio();
        audio.preload = 'auto';
        try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (_) { /* optional API */ }
        audio.addEventListener('timeupdate', () => this.onTime());
        audio.addEventListener('play', () => this.renderState());
        audio.addEventListener('pause', () => { this.renderState(); this.saveAll(); });
        audio.addEventListener('ended', () => this.nextChapter());
        audio.addEventListener('error', () => this.fail(audio.error));
        this.audio = audio;
        this.bindMediaSession();
        return audio;
    }

    bindMediaSession() {
        const session = navigator.mediaSession;
        if (!session) return;
        const handlers = {
            play: () => this.resume(),
            pause: () => this.pause(),
            seekbackward: details => this.seekBy(-(details?.seekOffset || 15)),
            seekforward: details => this.seekBy(details?.seekOffset || 30),
            seekto: details => this.seekToMs((details?.seekTime || 0) * 1000),
            previoustrack: () => this.previousChapter(),
            nexttrack: () => this.nextChapter(),
        };
        for (const [action, handler] of Object.entries(handlers)) {
            try { session.setActionHandler(action, handler); } catch (_) { /* unsupported action */ }
        }
    }

    // Load chapter `index` at `ms` and play. Resolves once playback was requested.
    async load(index, ms) {
        const chapter = this.chapters[index];
        if (!chapter) return;
        const audio = this.ensureAudio();
        this.index = index;
        this.unit = null;
        this.showBar(true);
        this.$('listen-resume').hidden = true;
        this.$('listen-message').textContent = '';
        this.$('listen-reload').hidden = true;
        this.$('listen-title').textContent = chapter.title;
        if ('MediaMetadata' in window && navigator.mediaSession) {
            navigator.mediaSession.metadata = new MediaMetadata({ title: chapter.title, artist: this.book.author || '', album: this.book.title });
        }
        const rate = this.saved()?.rate || audio.playbackRate || 1;
        audio.src = chapter.url;
        audio.defaultPlaybackRate = rate;
        audio.playbackRate = rate;
        this.failed = false;
        const start = Math.max(0, Math.min(ms, chapter.duration_ms)) / 1000;
        // play() runs now, inside the tap (iOS refuses it later); the seek waits for metadata.
        this.pendingStart = start > 0 ? start : null;
        if (start > 0) {
            const seek = () => { audio.currentTime = start; this.pendingStart = null; };
            if (audio.readyState >= 1) seek(); else audio.addEventListener('loadedmetadata', seek, { once: true });
        }
        try { await audio.play(); } catch (error) { if (error?.name !== 'AbortError') this.fail(error); }
    }

    // Chapter ids in reading order, from the reader's manifest.
    readingOrder() {
        const state = this.reader.continuousReader;
        const segments = (state?.manifest?.segments || [])
            .filter(segment => segment.mode === state.mode)
            .sort((a, b) => a.ordinal - b.ordinal);
        const ids = segments.flatMap(segment => (segment.chapter_ids || []).map(Number));
        return ids.length ? ids : this.chapters.map(item => item.chapter_id);
    }

    listenFromReadingPosition() {
        const marker = this.reader.continuousReader?.currentMarker;
        const saved = this.saved();
        const chapterId = Number(String(marker?.paragraph_id || '').split('.')[0]) || this.chapters[0].chapter_id;
        let index = this.chapters.findIndex(item => item.chapter_id === chapterId);
        if (index < 0) {
            // This chapter has no current audio: start at the next one that does.
            const order = this.readingOrder();
            const here = order.indexOf(chapterId);
            index = this.chapters.findIndex(item => order.indexOf(item.chapter_id) > here);
            if (index < 0) {
                this.showBar(true);
                this.$('listen-message').textContent = 'No audio from here on yet.';
                return Promise.resolve();
            }
        }
        const timings = this.chapters[index].timings;
        let ms;
        if (saved && marker && saved.paragraph_id === nearestUnit(timings, marker.paragraph_id)?.paragraph_id
            && saved.chapter_id === this.chapters[index].chapter_id) {
            ms = saved.ms;  // still on the paragraph the audio was paused in
        } else {
            ms = marker ? nearestUnit(timings, marker.paragraph_id).start_ms : 0;
        }
        this.startedAt = unitAt(timings, ms).paragraph_id;
        this.following = true;
        return this.load(index, ms);
    }

    resumeSaved() {
        const saved = this.saved();
        const index = saved ? this.chapters.findIndex(item => item.chapter_id === saved.chapter_id) : -1;
        if (index < 0) return this.listenFromReadingPosition();
        this.startedAt = unitAt(this.chapters[index].timings, saved.ms).paragraph_id;
        this.following = true;
        return this.load(index, saved.ms);
    }

    resume() {
        if (!this.audio || this.index < 0) return this.resumeSaved();
        return this.audio.play().catch(error => { if (error?.name !== 'AbortError') this.fail(error); });
    }

    pause() { this.audio?.pause(); }

    seekToMs(ms) {
        if (!this.audio) return;
        const duration = Number.isFinite(this.audio.duration) ? this.audio.duration * 1000 : this.chapters[this.index]?.duration_ms || 0;
        this.audio.currentTime = Math.max(0, Math.min(ms, duration)) / 1000;
        this.dirty = true;
        this.onTime();
    }

    seekBy(seconds) { if (this.audio) this.seekToMs(this.audio.currentTime * 1000 + seconds * 1000); }

    setRate(rate) {
        if (this.audio) { this.audio.playbackRate = rate; this.audio.defaultPlaybackRate = rate; }
        this.$('listen-rate').textContent = `${rate}×`;
        this.saveLocal();
    }

    async nextChapter() {
        this.saveServer();
        if (this.index + 1 >= this.chapters.length) { this.pause(); this.renderState(); return; }
        await this.load(this.index + 1, 0);
    }

    async previousChapter() {
        if (this.audio && this.audio.currentTime > 5) return this.seekToMs(0);
        if (this.index > 0) await this.load(this.index - 1, 0);
    }

    position() {
        if (!this.audio || this.index < 0) return null;
        const ms = Math.round(this.audio.currentTime * 1000);
        return { ms, ...unitAt(this.timings, ms), chapter_id: this.chapters[this.index].chapter_id };
    }

    onTime() {
        if (this.pendingStart !== null) return;  // still at 0:00, before the seek to the resume point
        const position = this.position();
        if (!position) return;
        if (!this.audio.paused) this.dirty = true;
        if (position.paragraph_id !== this.unit) {
            this.unit = position.paragraph_id;
            this.follow();
        }
        this.highlight();
        const now = Date.now();
        if (now - this.lastLocal > LOCAL_EVERY_MS) this.saveLocal();
        if (now - this.lastServer > SERVER_EVERY_MS && !this.audio.paused) this.saveServer();
    }

    highlight() {
        const content = document.getElementById('continuous-reader-content');
        if (!content) return;
        for (const element of content.querySelectorAll('.listen-current')) {
            if (element.dataset.readerAnchor !== this.unit) element.classList.remove('listen-current');
        }
        if (!this.unit || !this.audio) return;
        for (const element of content.querySelectorAll(`[data-reader-anchor="${this.unit}"]`)) element.classList.add('listen-current');
    }

    // Show the page holding the spoken unit (loading its section if needed).
    async follow(force = false) {
        if (!this.following && !force) return;
        const position = this.position();
        if (!position) return;
        const reader = this.reader;
        const marker = { paragraph_id: position.paragraph_id, offset: position.offset };
        this.navigating = true;
        try {
            const page = reader.pagination?.pages?.length ? reader.findContinuousPageForMarker(marker) : -1;
            const loaded = page >= 0 && reader.pagination.pages[page]?.includes(`data-reader-anchor="${position.paragraph_id}"`);
            if (loaded) {
                if (page !== reader.pagination.currentPage) {
                    reader.continuousReader.forwardTurn = page === reader.pagination.currentPage + 1;
                    reader.pagination.currentPage = page;
                    reader.displayCurrentPage();
                }
            } else {
                await reader.loadContinuousReaderAt(marker, position.chapter_id);
            }
        } finally {
            this.navigating = false;
        }
        this.highlight();
    }

    saveLocal() {
        const position = this.position();
        if (!position) return;
        this.lastLocal = Date.now();
        try {
            localStorage.setItem(this.key, JSON.stringify({
                chapter_id: position.chapter_id, paragraph_id: position.paragraph_id, ms: position.ms,
                title: this.chapters[this.index].title,
                rate: this.audio.playbackRate, at: new Date().toISOString(),
            }));
        } catch (_) { /* private mode */ }
    }

    // The audio position becomes the summary mode's reading position.
    saveServer() {
        const position = this.position();
        const state = this.reader.continuousReader;
        // Only a position the audio actually reached since the last save: a paused
        // player must not overwrite where the reader has since paged to.
        if (!position || !state?.active || !this.dirty) return;
        this.dirty = false;
        this.lastServer = Date.now();
        const marker = {
            book_id: this.book.id, mode: 'summary', content_version: state.manifest?.content_version,
            chapter_id: position.chapter_id, paragraph_id: position.paragraph_id, offset: position.offset,
            ordinal: state.unitsById?.get(position.paragraph_id)?.ordinal, quote: '',
        };
        if (marker.ordinal === undefined) delete marker.ordinal;
        state.currentMarker = marker;
        this.reader.saveContinuousReader?.('listen');
    }

    saveAll() { this.saveLocal(); this.saveServer(); }

    renderState() {
        const playing = this.audio && !this.audio.paused;
        const button = this.$('listen-play');
        button.textContent = playing ? 'Pause' : 'Play';
        button.setAttribute('aria-label', playing ? 'Pause' : 'Play');
        this.$('listen-rate').textContent = `${this.rate()}×`;
        if (navigator.mediaSession) navigator.mediaSession.playbackState = playing ? 'playing' : 'paused';
    }

    // A failed load pauses and says why: signed out, offline, stale audio (skip ahead) or other.
    async fail(error) {
        if (this.failed) return;  // the error event and the play() rejection report the same failure
        this.failed = true;
        this.audio?.pause();
        this.saveLocal();
        this.showBar(true);
        this.renderState();
        const say = (text, reload = false) => {
            this.$('listen-message').textContent = text;
            this.$('listen-reload').hidden = !reload;
        };
        if (error?.name === 'NotAllowedError') return say('Tap Play to start listening.');
        let why = 'signin';
        try {
            const response = await fetch(this.chapters[this.index]?.url, { method: 'HEAD', credentials: 'include', cache: 'no-store', redirect: 'manual' });
            if (response.status === 404) why = 'stale';
            else if (response.ok && (response.headers.get('content-type') || '').startsWith('audio/')) why = 'other';
        } catch (_) { why = 'offline'; }
        if (why === 'stale') return this.nextChapter();
        if (why === 'offline') return say('Paused — you’re offline. Tap Play to try again.');
        if (why === 'other') return say('Couldn’t play this chapter. Tap Play to try again.');
        return say('Paused — sign in again to keep listening.', true);
    }
}
