// Pure helper for choosing the initial chapter-page reading mode.
// Loaded as a plain <script> in the page and exposed on `window`.
//
// View modes:
//   - "original"      always available (the source-language text)
//   - "modern"        ("Plain English") available iff chapter.modern_english_text
//   - "summary"       available iff chapter.summary
//   - "side-by-side"  available iff chapter.modern_english_text, wide screens only
//
// Rules:
//   1. Saved preference is valid for this chapter → honor it.
//   2. Otherwise (no saved preference, or saved one is incompatible)
//      → prefer Plain English when available, else Original.
(function (root) {
    "use strict";

    var DEFAULT_WITHOUT_MODERN = "original";

    function isModeAvailable(mode, ctx) {
        switch (mode) {
            case "original":
                return true;
            case "modern":
                return !!ctx.hasModern;
            case "summary":
                return !!ctx.hasSummary;
            case "side-by-side":
                return !!ctx.hasModern && !ctx.isScreenTooNarrow;
            default:
                return false;
        }
    }

    function resolveInitialChapterViewMode(opts) {
        var ctx = {
            hasModern: !!opts.hasModern,
            hasSummary: !!opts.hasSummary,
            isScreenTooNarrow: !!opts.isScreenTooNarrow,
        };
        if (opts.savedMode && isModeAvailable(opts.savedMode, ctx)) {
            return opts.savedMode;
        }
        return ctx.hasModern ? "modern" : DEFAULT_WITHOUT_MODERN;
    }

    root.resolveInitialChapterViewMode = resolveInitialChapterViewMode;
})(typeof window !== "undefined" ? window : globalThis);
