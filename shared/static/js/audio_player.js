// AudioPlayer: one per browsing session. Owns the <audio> element, the tracks, position,
// speed, the silent hold after a pause and the lock-screen controls. Knows nothing about
// pages: readers and player screens subscribe to it.
//
// A source (see audio_sources.js) supplies { book, tracks, place }. A track is
// { id, bookId, bookTitle, author, title, urls: [...], durationMs?, timings?, cover?, waitForPart? }.
// `place` (a PlaceKeeper) remembers where the audio got to.

export const RATES = [1, 1.25, 1.5, 1.75, 2];
const HOLD_MS = 30 * 60 * 1000;
const LOCAL_EVERY_MS = 5000;
const SERVER_EVERY_MS = 30000;

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

export class AudioPlayer {
    constructor({ rates = RATES, holdMs = HOLD_MS } = {}) {
        this.rates = rates;
        this.holdMs = holdMs;
        this.source = null;
        this.tracks = [];
        this.index = -1;
        this.audio = null;
        this.unit = null;           // the timed unit being spoken
        this.startedAt = null;      // the unit listening started from
        this.held = null;           // { ms, timer } while paused on silence
        this.pendingStart = null;   // seconds to seek to once the audio's metadata loads
        this.part = 0;              // which of the track's urls is playing
        this.partOffset = 0;        // seconds in the finished parts
        this.dirty = false;         // the audio moved since the last server save
        this.failed = false;
        this.message = '';
        this.needsSignIn = false;
        this.lastLocal = 0;
        this.lastServer = 0;
        this.listeners = new Set();
        window.addEventListener('pagehide', () => this.saveAll());
        document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.saveAll(); });
    }

    subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
    emit(what) { for (const fn of [...this.listeners]) fn(what); }

    get book() { return this.source?.book || null; }
    get track() { return this.tracks[this.index] || null; }
    get timings() { return this.track?.timings || []; }
    get active() { return this.index >= 0; }
    get playing() { return !!this.audio && !this.audio.paused && !this.held; }
    get rate() { return this.audio?.playbackRate || this.source?.place?.saved()?.rate || 1; }

    get durationMs() {
        if (this.track?.durationMs) return this.track.durationMs;
        return this.audio && Number.isFinite(this.audio.duration) ? this.audio.duration * 1000 : 0;
    }

    // The source's tracks must already be loaded: iOS only starts audio inside the tap.
    setSource(source) {
        if (this.source !== source) this.source?.finish?.();
        this.source = source;
        this.tracks = source.tracks;
        this.index = -1;
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
        audio.addEventListener('ended', () => { if (!this.held) this.onEnded(); });
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
            previoustrack: () => this.previousTrack(),
            nexttrack: () => this.nextTrack(),
        };
        for (const [action, handler] of Object.entries(handlers)) {
            try { session.setActionHandler(action, handler); } catch (_) { /* unsupported action */ }
        }
    }

    // Load track `index` at `ms` and play. Resolves once playback was requested.
    async load(index, ms, { part = 0, partOffset = 0 } = {}) {
        const track = this.tracks[index];
        if (!track) return;
        const audio = this.ensureAudio();
        this.endHold();
        this.index = index;
        this.unit = null;
        this.part = part;
        this.partOffset = partOffset;
        this.message = '';
        this.needsSignIn = false;
        this.failed = false;
        if ('MediaMetadata' in window && navigator.mediaSession) {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: track.title, artist: track.author || '', album: track.bookTitle || '',
                artwork: track.cover ? [{ src: track.cover }] : [],
            });
        }
        const rate = this.source?.place?.saved()?.rate || audio.playbackRate || 1;
        audio.src = track.urls[part];
        audio.defaultPlaybackRate = rate;
        audio.playbackRate = rate;
        const limit = track.durationMs ?? Infinity;
        const start = Math.max(0, Math.min(ms, limit) / 1000 - partOffset);
        // play() runs now, inside the tap (iOS refuses it later); the seek waits for metadata.
        this.pendingStart = start > 0 ? start : null;
        if (start > 0) {
            const seek = () => { audio.currentTime = start; this.pendingStart = null; };
            if (audio.readyState >= 1) seek(); else audio.addEventListener('loadedmetadata', seek, { once: true });
        }
        this.emit('track');
        try { await audio.play(); } catch (error) { if (error?.name !== 'AbortError') this.fail(error); }
    }

    resume() {
        if (!this.audio || this.index < 0) return Promise.resolve();
        if (this.held) return this.load(this.index, this.held.ms, { part: this.part, partOffset: this.partOffset });
        return this.audio.play().catch(error => { if (error?.name !== 'AbortError') this.fail(error); });
    }

    pause() {
        if (!this.playing) return;
        const ms = this.position().ms;
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

    // Stop listening: no audio, no silent hold, no player on screen.
    close() {
        if (!this.active) return;
        this.saveAll();
        this.endHold();
        this.audio?.pause();
        this.source?.finish?.();
        this.index = -1;
        this.unit = null;
        this.message = '';
        this.needsSignIn = false;
        this.emit('state');
    }

    seekToMs(ms) {
        if (!this.audio || this.index < 0) return;
        if (this.held) {
            this.held.ms = Math.max(0, Math.min(ms, this.track?.durationMs || ms));
            this.dirty = true;
            this.saveLocal();
            this.emit('time');
            return;
        }
        const seconds = Math.max(0, Math.min(ms, this.durationMs || ms)) / 1000;
        this.audio.currentTime = Math.max(0, seconds - this.partOffset);
        this.dirty = true;
        this.onTime();
    }

    seekBy(seconds) { if (this.audio && this.index >= 0) this.seekToMs(this.position().ms + seconds * 1000); }

    setRate(rate) {
        if (this.audio) { this.audio.playbackRate = rate; this.audio.defaultPlaybackRate = rate; }
        this.saveLocal();
        this.emit('state');
    }

    cycleRate() { this.setRate(this.rates[(this.rates.indexOf(this.rate) + 1) % this.rates.length]); }

    async nextTrack() {
        this.saveServer();
        if (this.index + 1 >= this.tracks.length) { this.audio?.pause(); this.source?.finish?.(); this.renderState(); return; }
        await this.load(this.index + 1, 0);
    }

    async previousTrack() {
        if (this.position()?.ms > 5000) return this.seekToMs(0);
        if (this.index > 0) await this.load(this.index - 1, 0);
    }

    async onEnded() {
        const track = this.track;
        if (track && this.part + 1 < track.urls.length) {
            this.partOffset += Number.isFinite(this.audio.duration) ? this.audio.duration : 0;
            this.part += 1;
            const ready = await track.waitForPart?.(this.part);
            if (this.track !== track) return;
            if (ready === false) return this.fail(new Error('part not ready'));
            this.audio.src = track.urls[this.part];
            this.audio.play().catch(error => { if (error?.name !== 'AbortError') this.fail(error); });
            return;
        }
        this.nextTrack();
    }

    position() {
        if (!this.audio || this.index < 0) return null;
        // Before the seek lands the element still reads 0:00; report where it is heading.
        const ms = this.held ? this.held.ms : Math.round((this.partOffset + (this.pendingStart ?? this.audio.currentTime)) * 1000);
        const spoken = this.timings.length ? unitAt(this.timings, ms) : { index: 0, paragraph_id: null, offset: 0 };
        return { ms, ...spoken, trackId: this.track.id, chapter_id: this.track.id };
    }

    onTime() {
        if (this.pendingStart !== null) return;  // still at 0:00, before the seek to the resume point
        const position = this.position();
        if (!position) return;
        if (!this.audio.paused) this.dirty = true;
        this.unit = position.paragraph_id;
        this.emit('time');
        const now = Date.now();
        if (now - this.lastLocal > LOCAL_EVERY_MS) this.saveLocal();
        if (now - this.lastServer > SERVER_EVERY_MS && !this.audio.paused) this.saveServer();
    }

    saveLocal() {
        const position = this.position();
        if (!position || !this.source?.place) return;
        this.lastLocal = Date.now();
        this.source.place.save(position, this.track.title, this.audio.playbackRate);
    }

    // Only a position the audio actually reached since the last save: a paused
    // player must not overwrite where the reader has since paged to.
    saveServer() {
        const position = this.position();
        if (!position || !this.dirty || !this.source?.place) return undefined;
        this.dirty = false;
        this.lastServer = Date.now();
        return this.source.place.saveServer(position);
    }

    saveAll() { this.saveLocal(); return this.saveServer(); }

    say(text) { this.message = text; this.needsSignIn = false; this.emit('error'); }

    renderState() {
        if (navigator.mediaSession) navigator.mediaSession.playbackState = this.playing ? 'playing' : 'paused';
        this.emit('state');
    }

    // A failed load pauses and says why: signed out, offline, stale audio (skip ahead) or other.
    async fail(error) {
        if (this.failed || this.index < 0) return;  // the error event and the play() rejection report the same failure
        this.failed = true;
        this.audio?.pause();
        this.saveLocal();
        this.renderState();
        if (error?.name === 'NotAllowedError') return this.say('Tap Play to start listening.');
        let why = 'signin';
        try {
            const response = await fetch(this.track?.urls[this.part], { method: 'HEAD', credentials: 'include', cache: 'no-store', redirect: 'manual' });
            if (response.status === 404) why = 'stale';
            else if (response.ok && (response.headers.get('content-type') || '').startsWith('audio/')) why = 'other';
        } catch (_) { why = 'offline'; }
        if (why === 'stale') return this.nextTrack();
        if (why === 'offline') return this.say('Paused — you’re offline. Tap Play to try again.');
        if (why === 'other') return this.say('Couldn’t play this chapter. Tap Play to try again.');
        this.message = 'Paused — sign in again to keep listening.';
        this.needsSignIn = true;
        return this.emit('error');
    }
}
