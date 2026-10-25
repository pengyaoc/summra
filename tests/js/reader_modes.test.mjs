// The shared continuous reader takes its modes, labels, widths and features
// from window.READER_CONFIG (ReaderConfig.to_client() on the server). These
// call the platform mixins directly with a stubbed config and DOM.
//
// Run: node --test tests/js/reader_modes.test.mjs

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const sharedJs = join(here, "..", "..", "shared", "static", "js");
const load = path => import(pathToFileURL(path).href);
const { readerUtilsMixin } = await load(join(sharedJs, "reader_utils.js"));
const { continuousReaderMixin } = await load(join(sharedJs, "continuous_reader.js"));
const { paginationMixin } = await load(join(sharedJs, "pagination.js"));

const single = (id, label) => ({
    id, label, layout: "single", members: [], library_label: label, min_width: null, narrow_fallback: [],
});
const sideBySide = (members, minWidth = 1024) => ({
    id: "side_by_side", label: "Side-by-Side", layout: "side_by_side", members,
    library_label: "Side by side", min_width: minWidth, narrow_fallback: ["plain", "original"],
});
const PLAINLY_MEMBERS = [
    { id: "original", label: "Original", cell_class: "original" },
    { id: "plain", label: "Plain English", cell_class: "modern" },
];
const config = (modes, defaultModes, features = {}) => ({
    app_name: "T", cache_db_name: "t", api_base: "/api", extra_page_blocks: "",
    default_modes: defaultModes, modes,
    features: { progress: true, illustrations: true, page_turn_hint: true, kindle: false, ...features },
});
const PLAINLY = config(
    [single("summary", "Summary"), single("original", "Original"), single("plain", "Plain English"), sideBySide(PLAINLY_MEMBERS)],
    ["plain", "original"],
);

function fakeElement() {
    const classes = new Set();
    return {
        textContent: "", innerHTML: "", className: "", onclick: null, attributes: {},
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
            toggle: (name, force) => (force ?? !classes.has(name)) ? classes.add(name) : classes.delete(name),
        },
        setAttribute(name, value) { this.attributes[name] = value; },
        querySelectorAll: () => [],
        querySelector: () => null,
    };
}

let elements;
let mediaQueries;
let wide;
beforeEach(() => {
    elements = new Map();
    mediaQueries = [];
    wide = true;
    globalThis.document = {
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, fakeElement());
            return elements.get(id);
        },
        querySelectorAll: () => [],
        querySelector: () => null,
        createElement: () => fakeElement(),
    };
    globalThis.window = {
        READER_CONFIG: PLAINLY,
        matchMedia: query => {
            mediaQueries.push(query);
            return { matches: wide, addEventListener() {} };
        },
    };
});

const makeApp = (overrides = {}) => Object.assign({}, readerUtilsMixin, continuousReaderMixin, overrides);
const manifestOffering = (offered, extra = {}) => ({
    content_version: 1, structure: [], segments: [],
    modes: ["summary", "original", "plain", "side_by_side"].map(mode => ({
        mode, availability: offered.includes(mode) ? "available" : "unavailable",
    })),
    ...extra,
});

async function openWith(manifest, savedMode) {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ success: true, manifest }) });
    window.authModule = {
        cacheReaderManifest: async () => {},
        getReaderState: async () => ({ book: savedMode ? { last_mode: savedMode } : null, modes: [] }),
    };
    const app = makeApp({
        clearAllPaginationData() {}, showOnlySections() {},
        setupContinuousReaderChrome() {}, setupContinuousReaderLifecycle() {},
        loadContinuousReaderAt: async () => {},
    });
    await app.showContinuousReader({ id: 1, title: "Book" });
    return app.continuousReader.mode;
}

test("test_available_modes_intersect_config_and_manifest", () => {
    window.READER_CONFIG = config([single("summary", "Summary")], ["summary"]);
    const app = makeApp();
    assert.deepEqual(app.readerAvailableModes(manifestOffering(["original", "summary"])), ["summary"]);
    assert.deepEqual(app.readerAvailableModes(manifestOffering(["original"])), []);
});

test("available modes follow config order and drop modes too wide for the screen", () => {
    const app = makeApp();
    const manifest = manifestOffering(["side_by_side", "plain", "original"]);
    assert.deepEqual(app.readerAvailableModes(manifest), ["original", "plain", "side_by_side"]);
    wide = false;
    assert.deepEqual(app.readerAvailableModes(manifest), ["original", "plain"]);
});

test("test_default_mode_follows_config_preference", async () => {
    assert.equal(await openWith(manifestOffering(["summary", "original", "side_by_side"])), "original");
    assert.equal(await openWith(manifestOffering(["summary", "original", "plain"])), "plain");
});

test("test_saved_mode_outside_config_falls_through", async () => {
    window.READER_CONFIG = config([single("summary", "Summary"), single("original", "Original")], ["original"]);
    assert.equal(await openWith(manifestOffering(["summary", "original", "plain"]), "plain"), "original");
    assert.equal(await openWith(manifestOffering(["summary", "original", "plain"]), "summary"), "summary");
});

function chrome(manifest) {
    const app = makeApp({ continuousReader: { active: true, mode: "original", manifest }, currentBook: { title: "Book" } });
    app.setupContinuousReaderChrome();
    return document.getElementById("reader-mode-settings").classList.contains("hidden");
}

test("test_selector_hidden_with_one_available_mode", () => {
    document.getElementById("reader-mode-settings").classList.add("hidden");
    assert.equal(chrome(manifestOffering(["original"])), true);
    document.getElementById("reader-mode-settings").classList.remove("hidden");
    assert.equal(chrome(manifestOffering(["original"])), true);
    window.READER_CONFIG = config([single("summary", "Summary")], ["summary"]);
    assert.equal(chrome(manifestOffering(["summary", "original", "plain"])), true);
});

test("test_selector_shown_with_two_available_modes", () => {
    document.getElementById("reader-mode-settings").classList.add("hidden");
    assert.equal(chrome(manifestOffering(["original", "plain"])), false);
});

test("mode help copy names the first mode with a minimum width", () => {
    chrome(manifestOffering(["original", "plain", "side_by_side"]));
    assert.equal(document.getElementById("reader-mode-help").textContent,
        "Side-by-Side is available on screens 1024px wide or larger.");
    chrome(manifestOffering(["original", "plain"]));
    assert.equal(document.getElementById("reader-mode-help").textContent,
        "Side-by-Side is unavailable for this book.");
});

test("test_side_by_side_min_width_from_config", () => {
    window.READER_CONFIG = config([single("original", "Original"), single("plain", "Plain"), sideBySide(PLAINLY_MEMBERS, 900)], ["original"]);
    const app = makeApp();
    assert.equal(app.isContinuousReaderModeAvailable("plain"), true);
    assert.deepEqual(mediaQueries, []);
    wide = false;
    assert.equal(app.isContinuousReaderModeAvailable("side_by_side"), false);
    assert.deepEqual(mediaQueries, ["(min-width: 900px)"]);
});

test("the viewport listener watches each min_width mode's narrow range", () => {
    window.READER_CONFIG = config([single("original", "Original"), single("plain", "Plain"), sideBySide(PLAINLY_MEMBERS, 900)], ["original"]);
    globalThis.document.addEventListener = () => {};
    window.addEventListener = () => {};
    window.setInterval = () => {};
    const app = makeApp();
    app.setupContinuousReaderLifecycle();
    assert.deepEqual(mediaQueries, ["(max-width: 899px)"]);
});

async function narrowFallback(offered) {
    wide = false;
    const statuses = [];
    const switched = [];
    const app = makeApp({
        continuousReader: { active: true, mode: "side_by_side", manifest: manifestOffering(offered) },
        setupContinuousReaderChrome() {},
        setContinuousReaderStatus: message => statuses.push(message),
        async switchContinuousReaderMode(next) { switched.push(next); this.continuousReader.mode = next; },
    });
    await app.enforceContinuousReaderViewport();
    return { switched, statuses };
}

test("test_narrow_fallback_first_available", async () => {
    assert.deepEqual((await narrowFallback(["original", "plain", "side_by_side"])).switched, ["plain"]);
    assert.deepEqual((await narrowFallback(["original", "side_by_side"])).switched, ["original"]);
    assert.deepEqual((await narrowFallback(["side_by_side"])).switched, ["original"]);
    assert.deepEqual((await narrowFallback(["original", "plain", "side_by_side"])).statuses,
        ["Side-by-Side is available on screens 1024px wide or larger."]);
});

function render(mode, units) {
    const container = fakeElement();
    globalThis.document.getElementById = () => container;
    const app = makeApp({
        continuousReader: { active: true, mode, manifest: { structure: [] } },
        pagination: { pages: [] },
        continuousReaderBlock: text => ({ tag: "p", className: "", content: text }),
        initializePagination() {}, settleContinuousReaderMarker() {},
    });
    app.renderContinuousSegments([{ units }]);
    return container;
}

test("test_gap_copy_uses_mode_label", () => {
    const html = render("summary", [{ id: "u", chapter_id: 1, chapter_ordinal: 1, ordinal: 0, availability: "gap" }]).innerHTML;
    assert.ok(html.includes(">Summary unavailable for this section.</div>"), html);
    const plainHtml = render("plain", [{ id: "u", chapter_id: 1, chapter_ordinal: 1, ordinal: 0, availability: "gap" }]).innerHTML;
    assert.ok(plainHtml.includes(">Plain English unavailable for this section.</div>"), plainHtml);
});

test("test_sxs_cells_use_member_cell_class", () => {
    const members = [{ id: "original", label: "Left", cell_class: "left" }, { id: "plain", label: "Right", cell_class: "right" }];
    window.READER_CONFIG = config([single("original", "Original"), single("plain", "Plain"), sideBySide(members)], ["original"]);
    const container = render("side_by_side", [{
        id: "u", chapter_id: 1, chapter_ordinal: 1, ordinal: 0,
        members: { original: { available: true, content: "Old words" }, plain: { available: false } },
    }]);
    assert.equal(container.className, "continuous-reader-content chapter-side-by-side");
    assert.ok(container.innerHTML.startsWith(
        '<div class="side-by-side-headers"><div class="side-by-side-header">Left</div><div class="side-by-side-header">Right</div></div>'));
    assert.ok(container.innerHTML.includes(
        '<div class="side-by-side-cell left"><p>Old words</p></div><div class="side-by-side-cell right"><p class="reader-gap">Right unavailable for this section.</p></div>'));

    const seen = [];
    const candidate = {
        dataset: { readerAnchor: "u" }, textContent: "",
        querySelector: selector => { seen.push(selector); return { textContent: "one two" }; },
    };
    globalThis.document.createElement = () => ({ innerHTML: "", querySelectorAll: () => [candidate] });
    const app = makeApp({ continuousReader: { mode: "side_by_side", unitsById: new Map() }, pagination: { pages: ["a", "b"], currentPage: 1 } });
    assert.equal(app.continuousMarkerOffset({ dataset: { readerAnchor: "u", readerWordCount: "4" } }), 0.5);
    assert.deepEqual(seen, [".side-by-side-cell.left"]);
});

test("Plainly's side-by-side markup is unchanged", () => {
    const container = render("side_by_side", [{
        id: "u", chapter_id: 1, chapter_ordinal: 1, ordinal: 3, canonical_word_count: 2,
        members: { original: { available: true, content: "Old" }, plain: { available: true, content: "New" } },
    }]);
    assert.equal(container.innerHTML,
        '<div class="side-by-side-headers"><div class="side-by-side-header">Original</div><div class="side-by-side-header">Plain English</div></div>' +
        '<div class="side-by-side-row reader-alignment-row" data-reader-anchor="u" data-reader-ordinal="3" data-reader-chapter="1" data-reader-word-count="2">' +
        '<div class="side-by-side-cell original"><p>Old</p></div><div class="side-by-side-cell modern"><p>New</p></div></div>');
});

test("test_illustrations_off_renders_no_figure", () => {
    globalThis.withBasePath = path => path;
    const manifest = { structure: [{ chapter_id: 1, illustration_url: "illustrations/1/1.jpg" }] };
    const app = makeApp({ continuousReader: { manifest }, escapeHtml: value => value });
    assert.ok(app.continuousIllustrationHtml(1, "One").includes("<figure"));
    window.READER_CONFIG = config(PLAINLY.modes, PLAINLY.default_modes, { illustrations: false });
    assert.equal(app.continuousIllustrationHtml(1, "One"), "");
});

test("page_turn_hint off shows no hint", async () => {
    window.READER_CONFIG = config(PLAINLY.modes, PLAINLY.default_modes, { page_turn_hint: false });
    let authProbed = false;
    window.authModule = { initAuth: async () => { authProbed = true; }, hintSeen: () => false, markHintSeen() {} };
    const app = Object.assign({}, readerUtilsMixin, paginationMixin, { pagination: {} });
    await app.showPageTurnHintOnce();
    assert.equal(authProbed, false);
    assert.equal(app.pagination.hintShown, undefined);
});
