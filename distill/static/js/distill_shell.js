// The part of Distill that stays alive while pages change: the player and page loading.
import { AudioPlayer } from '../shared/js/audio_player.js';
import { PlayerUI } from '../shared/js/player_ui.js';
import { go, registerPage, startPageSwap } from '../shared/js/page_swap.js';
import { libraryPage } from './library_page.js';
import { bookPage } from './book_page.js';

const player = new AudioPlayer();
const ui = new PlayerUI(player, { coverFor: track => track.cover });
window.distillAudio = { player, ui, link: null, go: path => go(withBasePath(path)) };

let readerModule = null;
const loadReader = () => { readerModule ||= import('./distill_reader.js'); return readerModule; };
registerPage('reader', {
    async start(root) { (await loadReader()).openReader(root, player, ui); },
    async stop() { await (await loadReader()).closeReader(); },
});
registerPage('library', libraryPage(player));
registerPage('book', bookPage(player));

const base = window.APP_BASE_PATH || '';
const PAGES = /^\/$|^\/books\/[^/]+(\/read)?$/;
startPageSwap({
    root: '#page-root',
    canSwap: url => url.pathname.startsWith(base) && PAGES.test(url.pathname.slice(base.length) || '/'),
    beforeFullLoad: () => player.saveAll(),
});
// The reader's code is the biggest download. Fetch it while idle, so opening a book doesn't wait for it.
(window.requestIdleCallback || setTimeout)(() => loadReader());
