// Distill's reader: one shared reader for the whole session, opened and closed as pages change.
import { applyReaderPlatform } from '../shared/js/platform.js';
import { ReaderAudioLink } from '../shared/js/reader_audio_link.js';
import { go } from '../shared/js/page_swap.js';

class DistillReader {
    classifyUnit(text) { return JSON.parse(text); }
    selectBook(book) { return go(withBasePath(`/books/${book.slug}`) + '?return=' + encodeURIComponent(book.return_url || withBasePath('/'))); }
    showOnlySections() { document.getElementById('reader-shell').hidden = false; }
}
applyReaderPlatform(DistillReader);

let reader = null;
let link = null;
let opening = Promise.resolve();

function boot() {
    if (reader) return;
    reader = new DistillReader();
    reader.initReaderPlatform();
    reader.setupReadingSettings();
    reader.loadReadingPreferences();
    reader.setupPagination();
}

export function openReader(root, player, ui) {
    opening = (async () => {
        boot();
        const book = JSON.parse(root.dataset.book);
        reader.currentBook = book;
        reader.setupContinuousReaderExit();
        const params = new URLSearchParams(location.search);
        await reader.showContinuousReader(book, { chapter: params.get('chapter'), restart: params.get('restart') === '1' });
        link = new ReaderAudioLink(player, reader, {
            book, mode: 'summary', ui,
            storageKey: `distill-listen-${book.id}`,
            audioApi: `/api/books/${book.slug}/audio`,
        });
        window.distillAudio.link = link;
        await link.attach();
    })();
    return opening;
}

export async function closeReader() {
    await opening.catch(() => {});
    link?.detach();
    link = null;
    window.distillAudio.link = null;
    await Promise.race([Promise.resolve(reader?.leaveContinuousReader('navigation')).catch(() => {}), new Promise(resolve => setTimeout(resolve, 250))]);
    if (reader) reader.currentView = 'browse';
    document.getElementById('reader-shell').hidden = true;
}
