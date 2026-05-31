// Unit tests for resolveInitialChapterViewMode — the pure helper that
// picks the default reading mode on the chapter page.
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
