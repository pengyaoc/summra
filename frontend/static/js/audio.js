// Audio/TTS playback mixin for SummraApp — the persistent audio player,
// chunked-audio streaming playback, and TTS text-generation flow.
// Extracted from app.js (Phase 4b continuation); merged onto
// SummraApp.prototype via Object.assign in app.js, so every method still
// reads/writes `this.*` exactly as before the split.
export const audioMixin = {
    setupPersistentPlayer() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const playPauseBtn = document.getElementById('player-play-pause');
        const stopBtn = document.getElementById('player-stop');
        const progressBar = document.querySelector('.progress-bar');
        const progressFill = document.getElementById('progress-fill');
        const currentTimeSpan = document.getElementById('current-time');
        const totalTimeSpan = document.getElementById('total-time');

        playPauseBtn.addEventListener('click', () => {
            if (persistentAudio.paused) {
                persistentAudio.play();
                this.currentPlayback.isPlaying = true;
            } else {
                persistentAudio.pause();
                this.currentPlayback.isPlaying = false;
            }
        });

        // The player's play/pause icon and the summary's Listen button both
        // follow the audio element, wherever playback was started or paused.
        const syncControls = () => {
            this.renderPlayerPlayPause(!persistentAudio.paused);
            this.renderListenButton();
        };
        ['play', 'pause', 'emptied', 'ended'].forEach(event => persistentAudio.addEventListener(event, syncControls));
        this.renderPlayerPlayPause(false);

        stopBtn.addEventListener('click', () => {
            this.stopPlayback();
        });

        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            persistentAudio.currentTime = percent * persistentAudio.duration;
        });

        persistentAudio.addEventListener('timeupdate', () => {
            if (persistentAudio.duration) {
                const percent = (persistentAudio.currentTime / persistentAudio.duration) * 100;
                progressFill.style.width = `${percent}%`;
                currentTimeSpan.textContent = this.formatTime(persistentAudio.currentTime);
                totalTimeSpan.textContent = this.formatTime(persistentAudio.duration);
            }
        });

        persistentAudio.addEventListener('ended', () => {
            this.handleAudioEnded();
        });

        persistentAudio.addEventListener('loadedmetadata', () => {
            totalTimeSpan.textContent = this.formatTime(persistentAudio.duration);
        });
    },

    renderPlayerPlayPause(playing) {
        const button = document.getElementById('player-play-pause');
        if (!button) return;
        button.innerHTML = playing
            ? '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor"/></svg>'
            : '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>';
        button.setAttribute('aria-label', playing ? 'Pause' : 'Play');
        button.title = playing ? 'Pause' : 'Play';
    },

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    async stopPlayback() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const persistentPlayer = document.getElementById('persistent-player');

        persistentAudio.pause();
        persistentAudio.currentTime = 0;
        persistentAudio.src = '';

        const audioIdToCleanup = this.currentPlayback.audioId;

        this.currentPlayback = {
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null
        };

        persistentPlayer.classList.add('hidden');
        this.renderPlayerPlayPause(false);
        this.renderListenButton();

        try {
            await fetch(`${this.apiBase}/tts/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ audio_id: audioIdToCleanup })
            });
        } catch (error) {
            console.error('Error stopping TTS:', error);
        }
    },

    async handleAudioEnded() {
        this.currentPlayback.currentChunk++;
        if (this.currentPlayback.currentChunk < this.currentPlayback.audioUrls.length) {
            await this.playNextChunk();
        } else {
            this.currentPlayback.isPlaying = false;

            const audioIdToCleanup = this.currentPlayback.audioId;
            if (audioIdToCleanup) {
                try {
                    await fetch(`${this.apiBase}/tts/stop`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ audio_id: audioIdToCleanup })
                    });
                } catch (error) {
                    console.error('Error cleaning up:', error);
                }
            }
        }
    },

    async playNextChunk() {
        const persistentAudio = document.getElementById('persistent-audio-element');
        const chunkUrl = this.currentPlayback.audioUrls[this.currentPlayback.currentChunk];
        const chunkIndex = this.currentPlayback.currentChunk;

        if (chunkIndex > 0) {
            const isReady = await this.waitForChunk(chunkUrl);
            if (!isReady) {
                alert(`Audio playback failed: Chunk ${chunkIndex + 1} could not be loaded.`);
                await this.stopPlayback();
                return;
            }
        }

        persistentAudio.src = chunkUrl;

        // Update MediaSession metadata for Bluetooth/lock screen
        this.updateMediaSessionMetadata();

        try {
            await persistentAudio.play();
            this.currentPlayback.isPlaying = true;
        } catch (error) {
            // A pause (or a new source) before playback starts rejects
            // play() with AbortError; that's the reader's choice, not a failure.
            if (error.name === 'AbortError') return;
            console.error('Error playing chunk:', error);
            alert('Failed to play audio chunk.');
            await this.stopPlayback();
        }
    },

    async waitForChunk(url, retries = 30) {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, { method: 'HEAD' });
                if (response.ok) return true;
            } catch (error) {
                // Chunk not ready yet
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        return false;
    },

    updateSummaryTTSButton() {
        const ttsBtn = document.getElementById('active-summary-tts-button');
        if (!ttsBtn) return;

        // Determine which tab is active
        const activeTab = document.querySelector('.summary-tab.active');
        if (!activeTab) return;

        const tabName = activeTab.dataset.tab;

        // Update button based on active tab
        const type = tabName === '2000-word' ? 'medium' : 'concise';
        const hasAudio = type === 'medium' ? this.mediumSummaryHasAudio : this.conciseSummaryHasAudio;
        const content = type === 'medium' ? this.mediumSummaryContent : this.conciseSummaryContent;
        ttsBtn.classList.toggle('hidden', !hasAudio);
        ttsBtn.onclick = () => this.onListenClick(type, content);
        this.renderListenButton();
    },

    // Listen toggles the summary's audio if it's already loaded in the
    // player; otherwise it starts it.
    onListenClick(type, content) {
        const audio = document.getElementById('persistent-audio-element');
        if (this.isListenLoaded(type)) {
            if (audio.paused) audio.play(); else audio.pause();
            return;
        }
        this.generateTTS(content, type);
    },

    isListenLoaded(type) {
        const id = this.listenAudioIds?.[`${this.currentBook?.id}:${type}`];
        return !!id && this.currentPlayback?.audioId === id;
    },

    // Listen → Preparing… → Pause / Resume. The book page's button follows
    // the summary tab on screen; others carry data-listen-type.
    renderListenButton() {
        const summaryButton = document.getElementById('active-summary-tts-button');
        const summaryType = document.querySelector('.summary-tab.active')?.dataset.tab === '2000-word' ? 'medium' : 'concise';
        if (summaryButton) this.renderListenButtonState(summaryButton, summaryType);
        document.querySelectorAll('[data-listen-type]').forEach(button => {
            this.renderListenButtonState(button, button.dataset.listenType);
        });
    },

    renderListenButtonState(button, type) {
        const audio = document.getElementById('persistent-audio-element');
        const icons = {
            play: '<path d="M8 5.5v13l11-6.5z" fill="currentColor"/>',
            pause: '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor"/>',
        };
        let state = 'idle';
        if (this.listenLoading === type) state = 'loading';
        else if (this.isListenLoaded(type)) state = audio && !audio.paused ? 'playing' : 'paused';
        const label = { idle: 'Listen', loading: 'Preparing…', playing: 'Pause', paused: 'Resume' }[state];
        const icon = state === 'loading'
            ? '<span class="listen-spinner" aria-hidden="true"></span>'
            : `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">${state === 'playing' ? icons.pause : icons.play}</svg>`;
        button.innerHTML = `${icon}<span>${label}</span>`;
        button.disabled = state === 'loading';
        button.classList.toggle('is-playing', state === 'playing');
        button.setAttribute('aria-pressed', String(state === 'playing'));
    },

    async generateTTS(text, type) {
        if (!text) {
            alert('No text available');
            return;
        }

        const cleanedText = this.cleanTextForTTS(text);
        this.listenLoading = type;
        this.renderListenButton();

        try {
            const audioId = `book_${this.currentBook.id}_${type}`;
            const textToSend = this.truncateAtSentenceBoundary(cleanedText, 5000);

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                this.listenAudioIds = { ...this.listenAudioIds, [`${this.currentBook.id}:${type}`]: data.audio_id };
                const audioUrls = data.streaming && data.audio_urls ? data.audio_urls : [data.audio_url];
                // Use better labels for lock screen display: "Quick Summary" or "Full Summary"
                const displayType = type === 'concise' ? 'Quick Summary' : 'Full Summary';
                this.startPersistentPlayback(
                    audioUrls,
                    this.currentBook.title,
                    displayType,
                    data.audio_id,
                    this.currentBook.author
                );
            } else {
                alert(`Error generating audio: ${data.error}`);
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
        } finally {
            this.listenLoading = null;
            this.renderListenButton();
        }
    },

    async generateChapterTTS(chapterNumber, text, buttonElement, contentType = 'summary') {
        if (!text) {
            alert('No text available');
            return;
        }

        const originalText = buttonElement.textContent;
        buttonElement.disabled = true;
        buttonElement.textContent = '⏳ Loading...';

        const cleanedText = this.cleanTextForTTS(text);
        const audioId = `book_${this.currentBook.id}_chapter_${chapterNumber}_${contentType}`;
        const chapterTitle = `Chapter ${chapterNumber}`;

        try {
            const maxChars = contentType === 'fulltext' ? 20000 : 5000;
            const textToSend = this.truncateAtSentenceBoundary(cleanedText, maxChars);

            const response = await fetch(`${this.apiBase}/tts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: textToSend,
                    id: audioId,
                    streaming: true
                })
            });

            const data = await response.json();

            if (data.success) {
                const audioUrls = data.streaming && data.audio_urls ? data.audio_urls : [data.audio_url];
                this.startPersistentPlayback(
                    audioUrls,
                    this.currentBook.title,
                    chapterTitle,
                    data.audio_id,
                    this.currentBook.author
                );
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            } else {
                alert(`Error generating audio: ${data.error}`);
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            alert('Error generating audio. Please try again.');
            buttonElement.textContent = originalText;
            buttonElement.disabled = false;
        }
    },

    updatePlayerInfo(bookTitle, chapterTitle) {
        document.getElementById('player-title').textContent = bookTitle;
        document.getElementById('player-subtitle').textContent = chapterTitle;
    },

    updateMediaSessionMetadata() {
        // Update MediaSession API for Bluetooth/CarPlay/Android Auto/lock screen
        if ('mediaSession' in navigator && this.currentPlayback) {
            const bookTitle = this.currentPlayback.bookTitle || 'Unknown Book';
            const chapterTitle = this.currentPlayback.chapterTitle || 'Summary';
            const author = this.currentPlayback.author || 'Unknown Author';

            // Get book cover URL if available (covers are stored as .jpg/.webp)
            const coverUrl = this.currentBook && this.currentBook.cover_image_url
                ? window.location.origin + this.coverSources(this.currentBook.cover_image_url).jpg
                : null;

            // Format: Title = "{book name} by {author name}", Artist = "Quick Summary" or "Full Summary" or "Chapter X"
            const displayTitle = `${bookTitle} by ${author}`;

            // Set metadata
            navigator.mediaSession.metadata = new MediaMetadata({
                title: displayTitle,
                artist: chapterTitle,
                album: 'Summra Audiobook Summaries',
                artwork: coverUrl ? [
                    { src: coverUrl, sizes: '512x512', type: 'image/jpeg' },
                    { src: coverUrl, sizes: '256x256', type: 'image/jpeg' },
                    { src: coverUrl, sizes: '128x128', type: 'image/jpeg' }
                ] : []
            });

            // Set up playback controls
            navigator.mediaSession.setActionHandler('play', () => {
                const playPauseBtn = document.getElementById('player-play-pause');
                if (playPauseBtn) playPauseBtn.click();
            });

            navigator.mediaSession.setActionHandler('pause', () => {
                const playPauseBtn = document.getElementById('player-play-pause');
                if (playPauseBtn) playPauseBtn.click();
            });

            navigator.mediaSession.setActionHandler('stop', () => {
                this.stopPlayback();
            });

            // Previous/Next track handlers (if multi-chunk)
            if (this.currentPlayback.audioUrls && this.currentPlayback.audioUrls.length > 1) {
                navigator.mediaSession.setActionHandler('previoustrack', () => {
                    if (this.currentPlayback.currentChunk > 0) {
                        this.currentPlayback.currentChunk--;
                        this.playNextChunk();
                    }
                });

                navigator.mediaSession.setActionHandler('nexttrack', () => {
                    if (this.currentPlayback.currentChunk < this.currentPlayback.audioUrls.length - 1) {
                        this.currentPlayback.currentChunk++;
                        this.playNextChunk();
                    }
                });
            }
        }
    },

    async startPersistentPlayback(audioUrls, bookTitle, chapterTitle, audioId = null, author = null) {
        const persistentPlayer = document.getElementById('persistent-player');

        this.currentPlayback = {
            isPlaying: true,
            currentChunk: 0,
            audioUrls: audioUrls,
            bookTitle: bookTitle,
            chapterTitle: chapterTitle,
            audioId: audioId,
            author: author
        };

        this.updatePlayerInfo(bookTitle, chapterTitle);
        persistentPlayer.classList.remove('hidden');
        await this.playNextChunk();
    },

    truncateAtSentenceBoundary(text, maxChars = 5000) {
        if (text.length <= maxChars) return text;

        let truncated = text.substring(0, maxChars);
        const sentenceEndPattern = /[.!?][\s]/g;
        let lastMatch = null;
        let match;

        while ((match = sentenceEndPattern.exec(truncated)) !== null) {
            lastMatch = match;
        }

        if (lastMatch) {
            truncated = truncated.substring(0, lastMatch.index + 2);
        } else {
            const lastSpace = truncated.lastIndexOf(' ');
            if (lastSpace > maxChars * 0.8) {
                truncated = truncated.substring(0, lastSpace);
            }
        }

        return truncated.trim();
    },

    cleanTextForTTS(text) {
        let cleaned = text;
        cleaned = cleaned.replace(/[""]/g, '"');
        cleaned = cleaned.replace(/['']/g, "'");
        cleaned = cleaned.replace(/[«»]/g, '"');
        cleaned = cleaned.replace(/…/g, '...');
        cleaned = cleaned.replace(/^#{1,6}\s+/gm, '');
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
        cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
        cleaned = cleaned.replace(/_([^_]+)_/g, '$1');
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
        cleaned = cleaned.replace(/^>\s+/gm, '');
        cleaned = cleaned.replace(/^[\-*_]{3,}\s*$/gm, '');
        cleaned = cleaned.replace(/^[\s]*[-*+]\s+/gm, '');
        cleaned = cleaned.replace(/^[\s]*\d+\.\s+/gm, '');
        cleaned = cleaned.replace(/<[^>]+>/g, '');
        cleaned = cleaned.replace(/[\[\]{}]/g, '');
        cleaned = cleaned.replace(/!+/g, '!');
        cleaned = cleaned.replace(/\?+/g, '?');
        cleaned = cleaned.replace(/\.{4,}/g, '...');
        cleaned = cleaned.replace(/[\u200B-\u200D\uFEFF]/g, '');
        cleaned = cleaned.replace(/\s+/g, ' ');
        cleaned = cleaned.replace(/\n+/g, ' ');
        cleaned = cleaned.replace(/[?!]{2,}/g, '!');
        cleaned = cleaned.trim();

        if (cleaned && !cleaned.match(/[.!?]$/)) {
            cleaned = cleaned + '.';
        }

        return cleaned;
    },
};
