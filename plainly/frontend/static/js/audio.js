// Audio for SummraApp: Plainly's Listen buttons, its generated summary speech, and
// the link between the shared audio player and the shared reader. The player itself
// lives in shared/js. Merged onto SummraApp.prototype in app.js.
import { AudioPlayer } from '../shared/js/audio_player.js';
import { PlayerUI } from '../shared/js/player_ui.js';
import { ReaderAudioLink } from '../shared/js/reader_audio_link.js';
import { GeneratedSpeechSource } from './generated_speech_source.js';

export const audioMixin = {
    setupPersistentPlayer() {
        this.audioPlayer = new AudioPlayer();
        this.playerUI = new PlayerUI(this.audioPlayer, { coverFor: track => track.cover });
        this.audioPlayer.subscribe(what => { if (what !== 'time') this.renderListenButton(); });
        const app = this;
        window.plainlyAudio = { player: this.audioPlayer, ui: this.playerUI, get link() { return app.readerAudioLink; } };
    },

    // The reader is open, or changed mode: connect it to any recording of what is on screen.
    async onContinuousReaderReady() {
        this.readerAudioLink?.detach();
        this.readerAudioLink = null;
        const opening = (this.readerAudioOpening = {});
        const state = this.continuousReader;
        const book = this.currentBook;
        const slug = book.slug || this.slugify(book.title);
        const audioMode = state.mode === 'side_by_side' ? await this.sideBySideAudioMode(slug) : state.mode;
        if (opening !== this.readerAudioOpening || !this.continuousReader?.active) return;
        const member = this.readerMode(state.mode)?.members?.find(item => item.id === audioMode);
        const link = new ReaderAudioLink(this.audioPlayer, this, {
            book: { id: book.id, slug, title: book.title, author: book.author, cover: this.bookCoverUrl(book) },
            mode: state.mode,
            storageKey: `plainly-listen-${book.id}-${audioMode}`,
            audioApi: `/api/books/${slug}/audio?mode=${audioMode}`,
            ui: this.playerUI,
            highlightCell: member?.cell_class || null,
        });
        this.readerAudioLink = link;
        await link.attach();
    },

    onContinuousReaderLeft() {
        this.readerAudioOpening = null;
        this.readerAudioLink?.detach();
        this.readerAudioLink = null;
    },

    // Side by side reads the Plain English recording if there is one, otherwise the original.
    async sideBySideAudioMode(slug) {
        try {
            const response = await fetch(withBasePath(`/api/books/${slug}/audio?mode=plain`));
            const data = response.ok ? await response.json() : null;
            return data?.chapters?.length ? 'plain' : 'original';
        } catch (_) { return 'original'; }
    },

    bookCoverUrl(book) {
        return book?.cover_image_url ? window.location.origin + this.coverSources(book.cover_image_url).jpg : null;
    },

    stopGeneratedSpeech(audioId) {
        fetch(`${this.apiBase}/tts/stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio_id: audioId }),
        }).catch(error => console.error('Error stopping TTS:', error));
    },

    playGeneratedSpeech(audioUrls, title, audioId) {
        const book = this.currentBook;
        const source = new GeneratedSpeechSource({
            urls: audioUrls, bookId: book.id, bookTitle: book.title, author: book.author, title, audioId,
            cover: this.bookCoverUrl(book), onFinish: () => this.stopGeneratedSpeech(audioId),
        });
        this.audioPlayer.setSource(source);
        return this.audioPlayer.load(0, 0);
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
        if (this.isListenLoaded(type)) {
            const player = this.audioPlayer;
            if (player.playing) player.pause(); else player.resume();
            return;
        }
        this.generateTTS(content, type);
    },

    isListenLoaded(type) {
        const id = this.listenAudioIds?.[`${this.currentBook?.id}:${type}`];
        return !!id && this.audioPlayer?.active && this.audioPlayer.source?.audioId === id;
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
        const icons = {
            play: '<path d="M8 5.5v13l11-6.5z" fill="currentColor"/>',
            pause: '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor"/>',
        };
        let state = 'idle';
        if (this.listenLoading === type) state = 'loading';
        else if (this.isListenLoaded(type)) state = this.audioPlayer.playing ? 'playing' : 'paused';
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
                this.playGeneratedSpeech(audioUrls, displayType, data.audio_id);
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
                this.playGeneratedSpeech(audioUrls, chapterTitle, data.audio_id);
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
