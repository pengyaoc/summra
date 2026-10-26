// Shared block renderer: the one render vocabulary for the web reader. A host
// app's classifyUnit(text) turns a reader unit into a block; blocksMixin
// renders it as {tag, className, content} for the continuous reader.
// shared/reader/blocks.py renders the same vocabulary for Kindle pages and
// must stay in step (tests/shared/test_block_parity.py).
//
// Block types: p, h, verse, li, quote, ul, ol, keypoints, table, image.
// Content never contains an element the paginator selects as a block,
// except a list's own <li>.

// What the DOM produces for a text node's innerHTML.
export function escapeText(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/ /g, '&nbsp;');
}

function quoteAttr(s) {
    return escapeText(s).replace(/"/g, '&quot;');
}

// 'markdown': escape source HTML, then inline Markdown (marked when loaded,
// else a few regexes). 'strict': escape, then only **bold** and *italic*.
export function formatInline(text, inline) {
    const escaped = escapeText((text || '').trim());
    if (inline === 'strict') {
        return escaped
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>');
    }
    if (typeof marked !== 'undefined' && typeof marked.parseInline === 'function') {
        return marked.parseInline(escaped);
    }
    return escaped
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^\s*](?:[^*\n]*?[^\s*])?)\*/g, '<em>$1</em>')
        .replace(/\b_([^_\n]+?)_\b/g, '<em>$1</em>');
}

export function renderBlock(block, { inline, imageBase = '' } = {}) {
    const fmt = text => formatInline(text, inline);
    const items = list => (list || []).map(item => `<li>${fmt(item)}</li>`).join('\n');
    const cells = (row, tag) => (row || []).map(cell => `<${tag}>${fmt(cell)}</${tag}>`).join(' ');
    switch (block?.type) {
        case 'h':
            return { tag: 'h3', className: 'reader-section-heading', content: fmt(block.text) };
        case 'verse':
            return { tag: 'p', className: 'reader-verse', content: (block.lines || []).map(fmt).join('<br>\n') };
        case 'li':
            return { tag: 'p', className: 'reader-list-item', content: fmt(block.text) };
        case 'quote':
            return { tag: 'blockquote', className: 'reader-quote', content: fmt(block.text) };
        case 'ul':
        case 'ol':
            return { tag: block.type, className: 'reader-list', content: items(block.items) };
        case 'keypoints':
            return { tag: 'ul', className: 'reader-keypoints', content: items(block.items) };
        case 'table': {
            const head = block.header?.length ? `<thead><tr>${cells(block.header, 'th')}</tr></thead> ` : '';
            const rows = (block.rows || []).map(row => `<tr>${cells(row, 'td')}</tr>`).join('\n');
            return { tag: 'table', className: 'reader-table', content: `${head}<tbody>${rows}</tbody>` };
        }
        case 'image': {
            const caption = block.caption ? ` <figcaption>${fmt(block.caption)}</figcaption>` : '';
            return { tag: 'figure', className: 'reader-figure', content: `<img src="${quoteAttr(imageBase)}${quoteAttr(block.src)}" alt="">${caption}` };
        }
        default:
            return { tag: 'p', className: '', content: fmt(block?.text) };
    }
}

// Host hook: classifyUnit(text) -> block.
export const blocksMixin = {
    continuousReaderBlock(text) {
        const cfg = this.readerConfig();
        return renderBlock(this.classifyUnit(text), { inline: cfg.inline, imageBase: cfg.image_base });
    },
};
