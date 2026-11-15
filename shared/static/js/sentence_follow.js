// Sentence timings of a recorded unit: which sentence is being said, and where it is in the
// unit's text. Recordings made from 2026-11-14 give each unit timing
// `sentences: [[start_ms, end_ms, head, chars], ...]`, where head is the sentence's first
// characters and chars its length, both without whitespace. Older ones have none.

// Index of the sentence said at `ms` (a sentence keeps the silence after it), or -1.
export function sentenceAt(unit, ms) {
    const sentences = unit?.sentences;
    if (!sentences?.length) return -1;
    let index = 0;
    for (let i = 1; i < sentences.length; i += 1) {
        if (sentences[i][0] <= ms) index = i; else break;
    }
    return index;
}

// [[from, to), ...] of each sentence in `text` (the unit's shown text without whitespace),
// found in order; the page may add text the audio does not say, such as "1." or "•".
// Null when any sentence is not found, so the caller highlights the paragraph instead.
export function locateSentences(text, sentences) {
    if (!sentences?.length) return null;
    const ranges = [];
    let from = 0;
    for (const [, , head, chars] of sentences) {
        const at = text.indexOf(head, from);
        if (at < 0 || at + chars > text.length) return null;
        ranges.push([at, at + chars]);
        from = at + chars;
    }
    return ranges;
}
