// The Listen button on the home and book pages: plays through the shell's player,
// starting from the book's saved reading place. No reader needed.
import { RecordedBookSource } from '../shared/js/audio_sources.js';
import { PlaceKeeper, listenFrom } from '../shared/js/reader_audio_link.js';

const MODE = 'summary';

// Returns a function that undoes it, for when the page goes away.
export function startListenButton(root, player) {
    const button = root.querySelector('[data-listen-book]');
    if (!button) return () => {};
    const { listenBook, listenSlug, listenTitle, listenAuthor, listenCover } = button.dataset;
    const id = Number(listenBook);
    const book = { id, slug: listenSlug, title: listenTitle, author: listenAuthor, cover: listenCover || null };
    const playing = player.source?.book.id === id ? player.source : null;
    const place = playing?.place || new PlaceKeeper({ bookId: id, mode: MODE, storageKey: `distill-listen-${id}` });
    const source = playing || new RecordedBookSource({ audioApi: `/api/books/${listenSlug}/audio`, book, place });

    const isThisBook = () => player.active && player.book?.id === id;
    const render = () => { button.textContent = isThisBook() && player.playing ? 'Pause' : 'Listen'; };
    const unsubscribe = player.subscribe(render);
    let gone = false;
    (async () => {
        const [tracks] = await Promise.all([source.load(), place.load()]);
        if (gone) return;
        if (!tracks.length) { button.remove(); return; }
        button.disabled = false;
        render();
        button.addEventListener('click', () => {
            if (isThisBook()) return player.playing ? player.pause() : player.resume();
            return listenFrom(player, source, place.readingMarker, place.manifest, MODE);
        });
    })().catch(() => { if (!gone) button.remove(); });
    return () => { gone = true; unsubscribe(); };
}
