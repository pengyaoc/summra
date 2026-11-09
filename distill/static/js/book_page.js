// The book page: Listen and "mark as unread".
import { startListenButton } from './listen_home.js';
import { go } from '../shared/js/page_swap.js';

export function bookPage(player) {
    let stopListen = () => {};
    return {
        start(root) {
            stopListen = startListenButton(root, player);
            const unfinished = root.querySelector('.distill-unfinish');
            unfinished?.addEventListener('click', async () => {
                unfinished.disabled = true;
                try {
                    const id = Number(unfinished.dataset.bookId);
                    const response = await fetch(withBasePath(`/api/progress/v2/books/${id}/status`), {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: unfinished.dataset.readingStatus }),
                    });
                    if (!response.ok) throw new Error();
                    go(location.href, { push: false, scroll: scrollY });
                } catch (_) {
                    root.querySelector('#distill-book-status').textContent = 'Could not update this book. Please try again.';
                    unfinished.disabled = false;
                }
            });
        },
        stop() { stopListen(); },
    };
}
