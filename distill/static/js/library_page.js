// The library page: Listen, filters and search suggestions.
import { startListenButton } from './listen_home.js';
import { go } from '../shared/js/page_swap.js';

function startFilters(root, cleanups) {
    var form = root.querySelector('.distill-filters');
    if (!form) return;
    if (!form) return;
    var toggle = form.querySelector('.distill-filter-toggle');
    var panel = form.querySelector('.distill-filter-panel');
    toggle.addEventListener('click', function () {
        toggle.setAttribute('aria-expanded', String(panel.classList.toggle('is-open')));
    });
    var selects = form.querySelectorAll('select');
    for (var i = 0; i < selects.length; i++) {
        selects[i].addEventListener('change', function () { form.requestSubmit(); });
    }
    var input = form.querySelector('[name="q"]');
    var menu = form.querySelector('.distill-search-menu');
    var list = root.querySelector('#distill-search-options');
    var feedback = form.querySelector('.distill-search-feedback');
    var catalog = JSON.parse(root.querySelector('#distill-search-catalog').textContent);
    var matches = [], active = -1, composing = false;
    function close() {
        menu.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        active = -1;
    }
    function select(index) {
        active = index;
        for (var j = 0; j < list.children.length; j++) {
            list.children[j].setAttribute('aria-selected', j === active ? 'true' : 'false');
        }
        if (active >= 0) {
            input.setAttribute('aria-activedescendant', list.children[active].id);
            list.children[active].scrollIntoView({block: 'nearest'});
        } else input.removeAttribute('aria-activedescendant');
    }
    function openBook(index) {
        if (matches[index]) go((window.APP_BASE_PATH || '') + '/books/' + encodeURIComponent(matches[index].slug) + '?return=' + encodeURIComponent(location.pathname + location.search));
    }
    function suggest() {
        if (composing) return;
        var query = input.value.trim().toLocaleLowerCase();
        list.textContent = '';
        close();
        if (!query) return;
        matches = catalog.filter(function (book) {
            return (book.title + ' ' + book.author).toLocaleLowerCase().indexOf(query) !== -1;
        }).sort(function (a, b) {
            // Prefer titles beginning with the query to matches inside a name.
            return (b.title.toLocaleLowerCase().indexOf(query) === 0 ? 1 : 0) -
                   (a.title.toLocaleLowerCase().indexOf(query) === 0 ? 1 : 0);
        }).slice(0, 6);
        matches.forEach(function (book, index) {
            var option = document.createElement('li');
            option.id = 'distill-suggestion-' + index;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');
            var title = document.createElement('strong');
            title.textContent = book.title;
            title.lang = book.lang || 'en';
            option.appendChild(title);
            if (book.author && book.author.trim()) {
                var author = document.createElement('span');
                author.textContent = book.author;
                option.appendChild(author);
            }
            option.addEventListener('mousedown', function (event) { event.preventDefault(); });
            option.addEventListener('click', function () { openBook(index); });
            list.appendChild(option);
        });
        feedback.textContent = matches.length ? matches.length + ' suggested ' + (matches.length === 1 ? 'book' : 'books') + '. Use arrow keys to choose.' : 'No matching books in the selected filters.';
        menu.hidden = false;
        input.setAttribute('aria-expanded', 'true');
    }
    input.addEventListener('input', suggest);
    input.addEventListener('focus', suggest);
    input.addEventListener('compositionstart', function () { composing = true; close(); });
    input.addEventListener('compositionend', function () { composing = false; suggest(); });
    input.addEventListener('keydown', function (event) {
        if (composing || event.isComposing || event.keyCode === 229) return;
        if (event.key === 'Escape') { close(); return; }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (menu.hidden) suggest();
            if (!matches.length || menu.hidden) return;
            select((active + (event.key === 'ArrowDown' ? 1 : active < 0 ? 0 : -1) + matches.length) % matches.length);
        } else if (event.key === 'Enter' && !menu.hidden && active >= 0) {
            event.preventDefault();
            openBook(active);
        }
    });
    input.addEventListener('blur', close);
    function outside(event) {
        if (!form.querySelector('.distill-search-wrap').contains(event.target)) close();
    }
    document.addEventListener('click', outside);
    cleanups.push(function () { document.removeEventListener('click', outside); });
}

export function libraryPage(player) {
    const cleanups = [];
    return {
        start(root) {
            cleanups.push(startListenButton(root, player));
            startFilters(root, cleanups);
            // Back from another site restores a frozen page; its progress may be old.
            const onShow = event => { if (event.persisted) location.reload(); };
            window.addEventListener('pageshow', onShow);
            cleanups.push(() => window.removeEventListener('pageshow', onShow));
        },
        stop() { for (const undo of cleanups.splice(0)) undo(); },
    };
}
