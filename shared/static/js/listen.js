// Listen (shared reader platform): plays pre-rendered chapter audio in step with
// the continuous reader. One <audio> element; position is kept in localStorage
// (survives an iOS app kill) and saved to the server as the reading position of
// the app's audio mode.
//
// Page following: hands off, the page turns as the audio moves on (also inside a
// paragraph that runs onto the next page). A page turn by the reader stops
// following without touching the audio; "Back to audio" and "Play from here"
// are offered until following resumes. Play/pause never moves the page.

const RATES = [1, 1.25, 1.5, 1.75, 2];
const LOCAL_EVERY_MS = 5000;
const SERVER_EVERY_MS = 30000;
const HOLD_MS = 30 * 60 * 1000;

// Two seconds of silent 8 kHz WAV. iOS freezes a paused web app and lock-screen Play
// then never reaches it, so a paused player loops this to stay the active audio.
let silenceUrl = null;
function silence() {
    if (silenceUrl) return silenceUrl;
    const samples = 16000;
    const bytes = new Uint8Array(44 + samples).fill(128);
    const view = new DataView(bytes.buffer);
    const text = (at, value) => [...value].forEach((char, i) => view.setUint8(at + i, char.charCodeAt(0)));
    text(0, 'RIFF'); view.setUint32(4, 36 + samples, true); text(8, 'WAVEfmt ');
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 8000, true); view.setUint32(28, 8000, true); view.setUint16(32, 1, true); view.setUint16(34, 8, true);
    text(36, 'data'); view.setUint32(40, samples, true);
    silenceUrl = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
    return silenceUrl;
}

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
    // options: { audioApi: URL of {chapters:[{chapter_id, title, url, duration_ms, timings}]},
    //           storageKey: localStorage key for this book, mode: reader mode the audio follows }
    constructor(reader, book, { audioApi, storageKey, mode }) {
        this.reader = reader;
        this.book = book;
        this.audioApi = audioApi;
        this.mode = mode;
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
        this.key = storageKey;
        this.held = null;          // { ms, timer } while paused on silence
        this.holdMs = HOLD_MS;
    }

    get timings() { return this.chapters[this.index]?.timings || []; }

    get playing() { return !!this.audio && !this.audio.paused && !this.held; }

    $(id) { return document.getElementById(id); }

    async init() {
        try {
            const response = await fetch(withBasePath(this.audioApi), { credentials: 'include' });
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
        this.$('listen-play').addEventListener('click', () => (this.playing ? this.pause() : this.resume()));
        this.$('listen-back').addEventListener('click', () => this.seekBy(-15));
        this.$('listen-fwd').addEventListener('click', () => this.seekBy(30));
        this.$('listen-next').addEventListener('click', () => this.nextChapter());
        this.$('listen-rate').addEventListener('click', () => this.setRate(RATES[(RATES.indexOf(this.rate()) + 1) % RATES.length]));
        this.$('listen-follow').addEventListener('click', () => { this.setFollowing(true); this.follow(true); });
        this.$('listen-here').addEventListener('click', () => this.listenFromReadingPosition());
        this.$('listen-resume').addEventListener('click', () => this.resumeSaved());
        this.$('listen-reload').addEventListener('click', () => location.reload());
        this.$('listen-close').addEventListener('click', () => { this.pause(); this.stopSilence(); this.showBar(false); });
        window.addEventListener('pagehide', () => this.saveAll());
        document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.saveAll(); });
    }

    // A page turn by the reader (keys, taps, swipes, a contents jump), playing or
    // paused, stops following. Re-layouts and the player's own turns do not count.
    watchManualPaging() {
        const reader = this.reader;
        const byHand = name => {
            const original = reader[name].bind(reader);
            reader[name] = (...args) => {
                if (!this.navigating && this.index >= 0) this.setFollowing(false);
                return original(...args);
            };
        };
        byHand('navigateToNextPage');
        byHand('navigateToPreviousPage');
        // A chapter picked from the contents is a jump by hand; other reloads
        // (resize, settings) are re-layouts and keep following.
        document.addEventListener('click', event => {
            if (this.index >= 0 && event.target.closest?.('[data-reader-chapter-target]')) this.setFollowing(false);
        }, true);
        const displayed = reader.onContinuousPageDisplayed.bind(reader);
        reader.onContinuousPageDisplayed = () => { displayed(); this.highlight(); };
    }

    setFollowing(following) {
        this.following = following;
        this.$('listen-follow').hidden = following;
        this.$('listen-here').hidden = following;
    }

    showBar(visible) {
        const bar = this.$('listen-bar');
        if (bar.hidden !== visible) return;
        bar.hidden = !visible;
        this.highlight();
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
        // While held, these events are the silence's, not the chapter's.
        audio.addEventListener('timeupdate', () => { if (!this.held) this.onTime(); });
        audio.addEventListener('play', () => { if (!this.held) this.renderState(); });
        audio.addEventListener('pause', () => { if (!this.held) { this.renderState(); this.saveAll(); } });
        audio.addEventListener('ended', () => { if (!this.held) this.nextChapter(); });
        audio.addEventListener('error', () => { if (!this.held) this.fail(audio.error); });
        this.audio = audio;
        this.bindMediaSession();
        return audio;
    }

    bindMediaSession() {
        const session = navigator.mediaSession;
        if (!session) return;
        const handlers = {
            play: () => this.resume(),
            // Playing silence can make the lock screen offer Pause; while held, either button means play.
            pause: () => (this.held ? this.resume() : this.pause()),
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
        this.endHold();
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
        this.setFollowing(true);
        return this.load(index, ms);
    }

    resumeSaved() {
        const saved = this.saved();
        const index = saved ? this.chapters.findIndex(item => item.chapter_id === saved.chapter_id) : -1;
        if (index < 0) return this.listenFromReadingPosition();
        this.startedAt = unitAt(this.chapters[index].timings, saved.ms).paragraph_id;
        this.setFollowing(true);
        return this.load(index, saved.ms);
    }

    resume() {
        if (!this.audio || this.index < 0) return this.resumeSaved();
        if (this.held) return this.load(this.index, this.held.ms);
        return this.audio.play().catch(error => { if (error?.name !== 'AbortError') this.fail(error); });
    }

    pause() {
        if (!this.playing) return;
        const ms = Math.round(this.audio.currentTime * 1000);
        this.audio.pause();
        this.held = { ms, timer: setTimeout(() => this.stopSilence(), this.holdMs) };
        this.saveAll();
        this.renderState();
        this.audio.loop = true;
        this.audio.src = silence();
        // Without the silence the player is simply paused. Starting it marks the session as playing, so restate it.
        this.audio.play().catch(() => {}).finally(() => { if (this.held && navigator.mediaSession) navigator.mediaSession.playbackState = 'paused'; });
    }

    stopSilence() {
        if (!this.held) return;
        clearTimeout(this.held.timer);
        this.audio.pause();
    }

    endHold() {
        if (this.held) clearTimeout(this.held.timer);
        this.held = null;
        if (this.audio) this.audio.loop = false;
    }

    seekToMs(ms) {
        if (!this.audio) return;
        if (this.held) {
            this.held.ms = Math.max(0, Math.min(ms, this.chapters[this.index]?.duration_ms || 0));
            this.dirty = true;
            this.saveLocal();
            return;
        }
        const duration = Number.isFinite(this.audio.duration) ? this.audio.duration * 1000 : this.chapters[this.index]?.duration_ms || 0;
        this.audio.currentTime = Math.max(0, Math.min(ms, duration)) / 1000;
        this.dirty = true;
        this.onTime();
    }

    seekBy(seconds) { if (this.audio) this.seekToMs((this.held ? this.held.ms : this.audio.currentTime * 1000) + seconds * 1000); }

    setRate(rate) {
        if (this.audio) { this.audio.playbackRate = rate; this.audio.defaultPlaybackRate = rate; }
        this.$('listen-rate').textContent = `${rate}×`;
        this.saveLocal();
    }

    async nextChapter() {
        this.saveServer();
        if (this.index + 1 >= this.chapters.length) { this.audio?.pause(); this.renderState(); return; }
        await this.load(this.index + 1, 0);
    }

    async previousChapter() {
        if (this.audio && this.audio.currentTime > 5) return this.seekToMs(0);
        if (this.index > 0) await this.load(this.index - 1, 0);
    }

    position() {
        if (!this.audio || this.index < 0) return null;
        const ms = this.held ? this.held.ms : Math.round(this.audio.currentTime * 1000);
        return { ms, ...unitAt(this.timings, ms), chapter_id: this.chapters[this.index].chapter_id };
    }

    onTime() {
        if (this.pendingStart !== null) return;  // still at 0:00, before the seek to the resume point
        const position = this.position();
        if (!position) return;
        if (!this.audio.paused) this.dirty = true;
        const moved = position.paragraph_id !== this.unit;
        this.unit = position.paragraph_id;
        // Every tick, not only on a new paragraph: a long paragraph runs onto the next page.
        if (!this.navigating) this.follow();
        if (moved) this.highlight();
        const now = Date.now();
        if (now - this.lastLocal > LOCAL_EVERY_MS) this.saveLocal();
        if (now - this.lastServer > SERVER_EVERY_MS && !this.audio.paused) this.saveServer();
    }

    highlight() {
        const content = document.getElementById('continuous-reader-content');
        if (!content) return;
        const unit = this.$('listen-bar').hidden ? null : this.unit;  // no highlight once the player is closed
        for (const element of content.querySelectorAll('.listen-current')) {
            if (element.dataset.readerAnchor !== unit) element.classList.remove('listen-current');
        }
        if (!unit || !this.audio) return;
        for (const element of content.querySelectorAll(`[data-reader-anchor="${unit}"]`)) element.classList.add('listen-current');
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

    // The audio position becomes the audio mode's reading position.
    saveServer() {
        const position = this.position();
        const state = this.reader.continuousReader;
        // Only a position the audio actually reached since the last save: a paused
        // player must not overwrite where the reader has since paged to.
        if (!position || !state?.active || !this.dirty) return;
        this.dirty = false;
        this.lastServer = Date.now();
        const marker = {
            book_id: this.book.id, mode: this.mode, content_version: state.manifest?.content_version,
            chapter_id: position.chapter_id, paragraph_id: position.paragraph_id, offset: position.offset,
            ordinal: state.unitsById?.get(position.paragraph_id)?.ordinal, quote: '',
        };
        if (marker.ordinal === undefined) delete marker.ordinal;
        state.currentMarker = marker;
        this.reader.saveContinuousReader?.('listen');
    }

    saveAll() { this.saveLocal(); this.saveServer(); }

    renderState() {
        const playing = this.playing;
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
