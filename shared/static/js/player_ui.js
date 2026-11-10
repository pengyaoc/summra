// The mini and full players, drawn from an AudioPlayer's state. Controls with nothing
// behind them are hidden by the track data, never by which app this is.
const clock = ms => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;
const PLAY = '<path d="M7 4.5v15l12-7.5z"/>';
const PAUSE = '<rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/>';

export class PlayerUI {
    constructor(player, { coverFor }) {
        this.player = player;
        this.coverFor = coverFor;
        this.context = null;
        this.seeking = false;
        this.$ = id => document.getElementById(id);
        const on = (id, handler) => this.$(id).addEventListener('click', handler);
        on('player-mini-open', () => this.openFull());
        on('player-mini-play', () => this.toggle());
        on('player-mini-close', () => player.close());
        on('player-full-close', () => this.closeFull());
        on('player-stop', () => player.close());
        on('player-play', () => this.toggle());
        on('player-back', () => player.seekBy(-15));
        on('player-fwd', () => player.seekBy(30));
        on('player-prev', () => player.previousTrack());
        on('player-next', () => player.nextTrack());
        on('player-rate', () => player.cycleRate());
        on('player-chapters', () => this.toggleChapters());
        on('player-listen-here', () => this.context?.onListenHere());
        on('player-reload', () => location.reload());
        const seek = this.$('player-seek');
        seek.addEventListener('input', () => { this.seeking = true; this.$('player-time').textContent = clock(Number(seek.value)); });
        seek.addEventListener('change', () => { this.seeking = false; player.seekToMs(Number(seek.value)); });
        player.subscribe(what => this.render(what));
        this.render('track');
    }

    toggle() { return this.player.playing ? this.player.pause() : this.player.resume(); }

    openFull() {
        if (!this.player.active) return;
        this.$('player-full').hidden = false;
        document.body.classList.add('player-panel-open');
        this.render('track');
    }

    closeFull() {
        this.$('player-full').hidden = true;
        this.$('player-chapter-list').hidden = true;
        document.body.classList.remove('player-panel-open');
    }

    // { bookId, canListenHere, label(), onListenHere() } while a reader is on screen, else null
    setPageContext(context) { this.context = context; this.renderOffer(); }

    renderOffer() {
        const button = this.$('player-listen-here');
        const offer = !!this.context?.canListenHere && this.player.active && this.player.book?.id !== this.context.bookId;
        button.hidden = !offer;
        if (offer) this.$('player-listen-here-label').textContent = this.context.label();
    }

    toggleChapters() {
        const list = this.$('player-chapter-list');
        list.hidden = !list.hidden;
        if (list.hidden) return;
        const { player } = this;
        list.replaceChildren(...player.tracks.map((track, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = track.title;
            if (index === player.index) button.setAttribute('aria-current', 'true');
            button.addEventListener('click', () => { list.hidden = true; player.load(index, 0); });
            return button;
        }));
    }

    render(what) {
        const { player } = this;
        const active = player.active;
        this.$('player-mini').hidden = !active;
        if (!active) this.closeFull();
        this.renderMessage();
        if (!active) return;
        if (what === 'track') this.renderTrack();
        const position = player.position();
        const ms = position?.ms || 0;
        const duration = player.durationMs;
        const time = duration ? `${clock(ms)} / ${clock(duration)}` : clock(ms);
        this.$('player-mini-time').textContent = time;
        if (!this.seeking) {
            const seek = this.$('player-seek');
            seek.max = String(Math.round(duration));
            seek.value = String(ms);
            this.$('player-time').textContent = clock(ms);
            this.$('player-duration').textContent = duration ? clock(duration) : '';
        }
        if (what !== 'time') this.renderControls();
    }

    renderMessage() {
        const { player } = this;
        this.$('player-message-text').textContent = player.message;
        this.$('player-message').hidden = !player.message;
        this.$('player-reload').hidden = !player.needsSignIn;
    }

    renderControls() {
        const { player } = this;
        const playing = player.playing;
        for (const id of ['player-play', 'player-mini-play']) {
            const button = this.$(id);
            button.querySelector('svg').innerHTML = playing ? PAUSE : PLAY;
            button.setAttribute('aria-label', playing ? 'Pause' : 'Play');
        }
        this.$('player-rate').textContent = `${player.rate}×`;
    }

    renderTrack() {
        const { player } = this;
        const track = player.track;
        if (!track) return;
        const several = player.tracks.length > 1;
        const place = several ? `${track.bookTitle}, chapter ${player.index + 1} of ${player.tracks.length}` : track.bookTitle;
        this.$('player-title').textContent = track.title;
        this.$('player-book').textContent = place;
        this.$('player-mini-title').textContent = track.title;
        this.$('player-mini-book').textContent = track.bookTitle;
        for (const id of ['player-prev', 'player-next', 'player-chapters']) this.$(id).hidden = !several;
        const cover = this.coverFor(track);
        for (const id of ['player-cover', 'player-mini-cover']) {
            const holder = this.$(id);
            if (holder.dataset.for === String(track.bookId) && holder.childElementCount) continue;
            holder.dataset.for = String(track.bookId);
            if (cover) {
                const image = document.createElement('img');
                image.src = cover;
                image.alt = '';
                holder.replaceChildren(image);
            } else {
                const fallback = document.createElement('span');
                fallback.textContent = track.bookTitle;
                holder.replaceChildren(fallback);
            }
        }
        this.renderOffer();
        this.renderControls();
    }
}
