// ReaderAudioLink: ties an AudioPlayer to the continuous reader on screen. Headphones
// button, sentence highlight, automatic page turns and the "Listen from here instead"
// offer. PlaceKeeper remembers where a book's audio got to, with or without a reader.
//
// Highlight and page turns happen only when the book on screen is the one playing.
// A page turn by the reader stops following until the reader is back on the spoken page.
import { unitAt } from './audio_player.js';
import { RecordedBookSource } from './audio_sources.js';

export { unitAt };

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

function readingOrder(manifest, mode, tracks) {
    const ids = (manifest?.segments || [])
        .filter(segment => segment.mode === mode)
        .sort((a, b) => a.ordinal - b.ordinal)
        .flatMap(segment => (segment.chapter_ids || []).map(Number));
    return ids.length ? ids : tracks.map(track => track.id);
}

// Start `source` from a reading marker: the saved second if the reader is still on the
// paragraph the audio stopped in, otherwise the start of the paragraph being read.
// Must be called inside the tap, so nothing here waits on the network.
export function listenFrom(player, source, marker, manifest, mode) {
    const { tracks, place } = source;
    const saved = place.saved();
    const chapterId = Number(String(marker?.paragraph_id || '').split('.')[0]) || tracks[0].id;
    let index = tracks.findIndex(track => track.id === chapterId);
    if (index < 0) {
        // This chapter has no current audio: start at the next one that does.
        const order = readingOrder(manifest, mode, tracks);
        const here = order.indexOf(chapterId);
        index = tracks.findIndex(track => order.indexOf(track.id) > here);
        if (index < 0) { player.say('No audio from here on yet.'); return Promise.resolve(); }
    }
    const { timings } = tracks[index];
    let ms;
    if (saved && marker && saved.chapter_id === tracks[index].id
        && saved.paragraph_id === nearestUnit(timings, marker.paragraph_id)?.paragraph_id) {
        ms = saved.ms;  // still on the paragraph the audio was paused in
    } else {
        ms = marker ? nearestUnit(timings, marker.paragraph_id).start_ms : 0;
    }
    if (player.source !== source) { player.saveAll(); player.setSource(source); }
    player.startedAt = unitAt(timings, ms).paragraph_id;
    return player.load(index, ms);
}

export class PlaceKeeper {
    constructor({ bookId, mode, storageKey, manifest = null }) {
        this.bookId = bookId;
        this.mode = mode;
        this.storageKey = storageKey;
        this.manifest = manifest;
        this.reader = null;
        this.revision = null;
        this.readingMarker = null;
        this.loading = null;
    }

    saved() {
        try { return JSON.parse(localStorage.getItem(this.storageKey) || 'null'); } catch (_) { return null; }
    }

    save(position, title, rate) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify({
                chapter_id: position.chapter_id, paragraph_id: position.paragraph_id, ms: position.ms,
                title, rate, at: new Date().toISOString(),
            }));
        } catch (_) { /* private mode */ }
    }

    markerFor(position) {
        const units = this.reader?.continuousReader?.unitsById;
        const marker = {
            book_id: this.bookId, mode: this.mode, content_version: this.manifest?.content_version,
            chapter_id: position.chapter_id, paragraph_id: position.paragraph_id, offset: position.offset,
            ordinal: units?.get(position.paragraph_id)?.ordinal, quote: '',
        };
        if (marker.ordinal === undefined) delete marker.ordinal;
        return marker;
    }

    // With the book open in a reader, saves go through the reader so its own state stays right.
    bindReader(reader) { this.reader = reader; this.manifest = reader.continuousReader?.manifest || this.manifest; }
    unbindReader() { this.reader = null; this.revision = null; this.loading = null; }

    // The book's manifest and saved reading place, for when no reader is on screen.
    load() {
        this.loading ||= (async () => {
            await window.authModule.initAuth();
            const get = async path => {
                const response = await fetch(withBasePath(path), { credentials: 'include' });
                if (!response.ok) throw new Error(path);
                return response.json();
            };
            const [{ manifest }, { projection }] = await Promise.all([
                get(`/api/reader/books/${this.bookId}/manifest`), get(`/api/progress/v2/books/${this.bookId}`),
            ]);
            const saved = projection.modes.find(item => item.mode === this.mode);
            this.manifest = manifest;
            this.revision = saved?.revision ?? 0;
            this.readingMarker = saved?.current_marker || null;
        })();
        return this.loading;
    }

    async saveServer(position) {
        const state = this.reader?.continuousReader;
        if (state?.active) {
            state.currentMarker = this.markerFor(position);
            return this.reader.saveContinuousReader?.('listen');
        }
        const marker = this.markerFor(position);
        const queue = async () => {
            await this.load();
            marker.content_version = this.manifest?.content_version;
            const mutation = await window.authModule.queueReaderMutation({
                book_id: this.bookId, mode: this.mode, current_marker: marker, qualified_furthest_marker: null,
                event_cause: 'listen', active_seconds_delta: 0, sequential_boundaries_delta: 0, base_revision: this.revision,
            });
            this.revision = mutation?.projection?.modes?.find(item => item.mode === this.mode)?.revision ?? this.revision;
        };
        return queue().catch(() => {});
    }
}

const HEADPHONES = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="6" rx="1"/><rect x="17" y="14" width="4" height="6" rx="1"/></svg>';

export class ReaderAudioLink {
    // book: { id, slug, title, author, cover? }; audioApi: URL of the book's recordings
    constructor(player, reader, { book, mode, storageKey, audioApi, ui }) {
        this.player = player;
        this.reader = reader;
        this.book = book;
        this.mode = mode;
        this.ui = ui;
        const playing = player.source?.book.id === book.id ? player.source : null;
        this.place = playing?.place || new PlaceKeeper({ bookId: book.id, mode, storageKey });
        this.source = playing || new RecordedBookSource({ audioApi, book, place: this.place });
        this.following = true;
        this.navigating = false;
        this.detached = false;
        this.restore = [];
    }

    get matches() { return this.player.active && this.player.book?.id === this.book.id; }

    async attach() {
        await this.source.load();
        if (this.detached) return;
        this.place.bindReader(this.reader);
        this.wrapPaging();
        const unsubscribe = this.player.subscribe(what => this.onPlayer(what));
        this.restore.push(unsubscribe);
        this.ui.setPageContext({
            bookId: this.book.id,
            canListenHere: this.source.tracks.length > 0,
            label: () => this.listenHereLabel(),
            onListenHere: () => this.listenFromReadingPosition(),
        });
        this.following = this.matches ? this.spokenOnScreen() : true;
        this.renderButton();
        this.highlight();
    }

    detach() {
        this.detached = true;
        for (const undo of this.restore.splice(0)) undo();
        document.getElementById('listen-button')?.remove();
        this.clearHighlight();
        this.place.unbindReader();
        this.ui.setPageContext(null);
    }

    listenHereLabel() {
        const chapterId = Number(String(this.reader.continuousReader?.currentMarker?.paragraph_id || '').split('.')[0]);
        const track = this.source.tracks.find(item => item.id === chapterId);
        return track ? `${this.book.title}, ${track.title}` : this.book.title;
    }

    // Turns by the reader (keys, taps, swipes, a contents jump) stop following.
    // Re-layouts and the player's own turns do not count.
    wrapPaging() {
        const reader = this.reader;
        const wrap = (name, wrapper) => {
            const original = reader[name];
            reader[name] = wrapper(original.bind(reader));
            this.restore.push(() => { reader[name] = original; });
        };
        const byHand = original => (...args) => {
            if (!this.navigating && this.matches) this.setFollowing(false);
            return original(...args);
        };
        wrap('navigateToNextPage', byHand);
        wrap('navigateToPreviousPage', byHand);
        wrap('onContinuousPageDisplayed', original => () => {
            original();
            // Back on the spoken page by hand: follow again.
            if (!this.navigating && this.matches && !this.following && this.spokenOnScreen()) this.setFollowing(true);
            this.highlight();
        });
        const onClick = event => {
            if (this.matches && event.target.closest?.('[data-reader-chapter-target]')) this.setFollowing(false);
        };
        document.addEventListener('click', onClick, true);
        this.restore.push(() => document.removeEventListener('click', onClick, true));
    }

    setFollowing(following) { this.following = following; }

    spokenOnScreen() {
        const position = this.player.position();
        const { reader } = this;
        if (!position?.paragraph_id || !reader.pagination?.pages?.length) return false;
        const page = reader.findContinuousPageForMarker({ paragraph_id: position.paragraph_id, offset: position.offset });
        return page === reader.pagination.currentPage
            && !!reader.pagination.pages[page]?.includes(`data-reader-anchor="${position.paragraph_id}"`);
    }

    onPlayer(what) {
        if (what === 'state') this.renderButton();
        if (what === 'track') { if (this.matches) this.setFollowing(true); this.renderButton(); }
        if (what === 'time' || what === 'track') { if (!this.navigating) this.follow(); }
        if (what !== 'error') this.highlight();
    }

    renderButton() {
        const toolbar = document.querySelector('.reader-toolbar-right');
        let button = document.getElementById('listen-button');
        const wanted = this.source.tracks.length > 0 || this.player.active;
        if (!wanted || !toolbar) { button?.remove(); return; }
        if (!button) {
            button = document.createElement('button');
            button.type = 'button';
            button.id = 'listen-button';
            button.className = 'reader-toolbar-btn reader-icon-btn';
            button.title = 'Listen';
            button.setAttribute('aria-label', 'Listen');
            button.innerHTML = HEADPHONES;
            button.addEventListener('click', () => (this.player.active ? this.ui.openFull() : this.listenFromReadingPosition()));
            toolbar.prepend(button);
        }
        button.classList.toggle('is-listening', this.player.active);
    }

    listenFromReadingPosition() {
        this.setFollowing(true);
        const state = this.reader.continuousReader;
        return listenFrom(this.player, this.source, state?.currentMarker, state?.manifest, this.mode);
    }

    clearHighlight() {
        for (const element of document.querySelectorAll('#continuous-reader-content .listen-current')) element.classList.remove('listen-current');
    }

    highlight() {
        const content = document.getElementById('continuous-reader-content');
        if (!content) return;
        const unit = this.matches ? this.player.unit : null;
        for (const element of content.querySelectorAll('.listen-current')) {
            if (element.dataset.readerAnchor !== unit) element.classList.remove('listen-current');
        }
        if (unit) for (const element of content.querySelectorAll(`[data-reader-anchor="${unit}"]`)) element.classList.add('listen-current');
    }

    // Show the page holding the spoken unit (loading its section if needed).
    async follow() {
        if (!this.following || !this.matches) return;
        const position = this.player.position();
        if (!position?.paragraph_id) return;
        const { reader } = this;
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
}
