// Unit tests for reader mode selection and mode-specific progress.
//
// Loads the exact same file the browser loads (frontend/static/js/view_mode.js)
// inside a stub-window context, so production and tests stay in sync.
//
// Run: node --test tests/js/resolve_view_mode.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const sourcePath = join(here, "..", "..", "frontend", "static", "js", "view_mode.js");
const source = readFileSync(sourcePath, "utf8");

const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { resolveInitialChapterViewMode } = sandbox.window;

if (typeof resolveInitialChapterViewMode !== "function") {
    throw new Error("view_mode.js did not expose window.resolveInitialChapterViewMode");
}

// --- No saved preference: prefer Plain English when available ---

test("no saved preference + modern available → modern", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: null,
        hasModern: true,
        hasSummary: true,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "modern");
});

test("no saved preference + no modern → original (fallback)", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: null,
        hasModern: false,
        hasSummary: true,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "original");
});

test("empty-string saved preference is treated as unset → modern when available", () => {
    // localStorage.getItem returns "" for explicitly-set empty values; our old
    // `|| 'original'` would coerce that to 'original'. New helper treats
    // empty string the same as null and picks the new default.
    const mode = resolveInitialChapterViewMode({
        savedMode: "",
        hasModern: true,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "modern");
});

// --- Saved preference is respected when valid ---

test("saved 'original' is respected even when modern available", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "original",
        hasModern: true,
        hasSummary: true,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "original");
});

test("saved 'modern' is respected when modern available", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "modern",
        hasModern: true,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "modern");
});

test("saved 'summary' is respected when summary available", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "summary",
        hasModern: true,
        hasSummary: true,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "summary");
});

test("saved 'side-by-side' is respected on wide screen with modern", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "side-by-side",
        hasModern: true,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "side-by-side");
});

// --- Fallbacks when saved preference is incompatible ---
// New rule: invalid saved mode falls back to the new default
// (Plain English if available, else Original) — same as the no-saved case.

test("saved 'modern' but no modern available → original (no modern to fall back to)", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "modern",
        hasModern: false,
        hasSummary: true,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "original");
});

test("saved 'summary' but no summary → modern (new default applies)", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "summary",
        hasModern: true,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "modern");
});

test("saved 'summary' with no summary and no modern → original", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "summary",
        hasModern: false,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "original");
});

test("saved 'side-by-side' on narrow screen → modern (new default applies)", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "side-by-side",
        hasModern: true,
        hasSummary: false,
        isScreenTooNarrow: true,
    });
    assert.equal(mode, "modern");
});

test("saved 'side-by-side' but no modern available → original", () => {
    const mode = resolveInitialChapterViewMode({
        savedMode: "side-by-side",
        hasModern: false,
        hasSummary: false,
        isScreenTooNarrow: false,
    });
    assert.equal(mode, "original");
});

test("continuous reader restores each mode's latest in-session marker", async () => {
    const readerSourcePath = join(here, "..", "..", "frontend", "static", "js", "reader.js");
    const readerSource = readFileSync(readerSourcePath, "utf8")
        .replace("export const readerMixin =", "const readerMixin =");
    const queued = [];
    const readerSandbox = {
        clearTimeout,
        setTimeout,
        window: {
            authModule: {
                queueReaderMutation: async mutation => {
                    queued.push(mutation);
                    return mutation;
                },
            },
        },
    };
    vm.createContext(readerSandbox);
    vm.runInContext(readerSource, readerSandbox);
    const readerMixin = vm.runInContext("readerMixin", readerSandbox);
    const marker = (mode, ordinal) => ({
        mode, content_version: 1, chapter_id: 10,
        paragraph_id: `${mode}-${ordinal}`, offset: 0,
        quote: `${mode} ${ordinal}`, ordinal, word_position: ordinal * 10,
    });
    const originalSaved = marker("original", 1);
    const plainSaved = marker("plain", 4);
    const plainFurthest = marker("plain", 6);
    const originalCurrent = marker("original", 9);
    const originalFurthest = marker("original", 10);
    const loaded = [];
    const app = {
        currentBook: { id: 7 },
        continuousReader: {
            active: true, restoring: false, mode: "original",
            currentMarker: originalCurrent, furthestMarker: originalFurthest,
            state: {
                book: { book_id: 7, last_mode: "original" },
                modes: [
                    { book_id: 7, mode: "original", current_marker: originalSaved, furthest_marker: originalSaved, revision: 2 },
                    { book_id: 7, mode: "plain", current_marker: plainSaved, furthest_marker: plainFurthest, revision: 3 },
                ],
            },
        },
        isContinuousReaderModeAvailable: () => true,
        updateContinuousReaderProgress: () => {},
        mapContinuousMarker: async () => assert.fail("saved mode should not need marker mapping"),
        loadContinuousReaderAt: async function (destination, chapterId) {
            loaded.push({ destination, chapterId });
            this.continuousReader.restoring = false;
        },
    };
    app.saveContinuousReader = readerMixin.saveContinuousReader;

    await readerMixin.switchContinuousReaderMode.call(app, "plain");

    assert.equal(queued[0].mode, "original");
    assert.equal(app.continuousReader.state.modes[0].current_marker.paragraph_id, "original-9");
    assert.equal(app.continuousReader.mode, "plain");
    assert.equal(app.continuousReader.currentMarker.paragraph_id, "plain-4");
    assert.equal(app.continuousReader.furthestMarker.paragraph_id, "plain-6");
    assert.equal(loaded[0].destination.paragraph_id, "plain-4");

    app.continuousReader.currentMarker = marker("plain", 7);
    app.continuousReader.furthestMarker = marker("plain", 8);
    await readerMixin.switchContinuousReaderMode.call(app, "original");

    assert.equal(queued[1].mode, "plain");
    assert.equal(app.continuousReader.state.modes[1].current_marker.paragraph_id, "plain-7");
    assert.equal(app.continuousReader.mode, "original");
    assert.equal(app.continuousReader.currentMarker.paragraph_id, "original-9");
    assert.equal(app.continuousReader.furthestMarker.paragraph_id, "original-10");
    assert.equal(loaded[1].destination.paragraph_id, "original-9");
    assert.equal(app.continuousReader.state.book.last_mode, "plain");
});
