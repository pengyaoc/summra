// Listen from the home and book pages: the reader's Listener, driving audio without a reader on screen.
// The stand-in below gives it the book's real manifest and saved place, so the audio
// starts where the reading stopped and moves the same saved place.
import { Listener } from '../shared/js/listen.js';

const MODE = 'summary';
const button = document.querySelector('[data-listen-book]');

async function json(path) {
    const response = await fetch(withBasePath(path), { credentials: 'include' });
    if (!response.ok) throw new Error(path);
    return response.json();
}

async function start() {
    const { listenBook, listenSlug, listenTitle, listenAuthor } = button.dataset;
    const id = Number(listenBook);
    await window.authModule.initAuth();
    const [{ manifest }, { projection }] = await Promise.all([
        json(`/api/reader/books/${id}/manifest`), json(`/api/progress/v2/books/${id}`),
    ]);
    const saved = projection.modes.find(item => item.mode === MODE);
    let revision = saved?.revision ?? 0;
    const state = { active: true, mode: MODE, manifest, currentMarker: saved?.current_marker || null, unitsById: new Map() };
    const noPages = () => {};
    const reader = {
        continuousReader: state,
        navigateToNextPage: noPages,
        navigateToPreviousPage: noPages,
        onContinuousPageDisplayed: noPages,
        loadContinuousReaderAt: async () => {},
        async saveContinuousReader(cause) {
            const mutation = await window.authModule.queueReaderMutation({
                book_id: id, mode: MODE, current_marker: state.currentMarker, qualified_furthest_marker: null,
                event_cause: cause, active_seconds_delta: 0, sequential_boundaries_delta: 0, base_revision: revision,
            });
            revision = mutation?.projection?.modes?.find(item => item.mode === MODE)?.revision ?? revision;
        },
    };
    const listener = new Listener(reader, { id, title: listenTitle, author: listenAuthor }, {
        audioApi: `/api/books/${listenSlug}/audio`, storageKey: `distill-listen-${id}`, mode: MODE,
    });
    if (!await listener.init()) { button.remove(); return; }
    listener.showBar(false);  // the player appears when Listen is pressed
    window.distillListener = listener;  // also the e2e test's handle

    const renderState = listener.renderState.bind(listener);
    listener.renderState = () => {
        renderState();
        button.textContent = listener.playing ? 'Pause' : 'Listen';
    };
    button.disabled = false;
    button.addEventListener('click', () => {
        if (listener.playing) { listener.pause(); return; }
        listener.showBar(true);
        if (listener.index >= 0) listener.resume(); else listener.listenFromReadingPosition();
    });
}

if (button) start().catch(() => button.remove());
