// Unit tests for route_utils.js — the pure route-parsing helpers shared by
// handleRoute() and buildBreadcrumbs() in app.js.
//
// Loads the exact same file the browser loads, inside a stub-window context,
// so production and tests stay in sync (same pattern as
// resolve_view_mode.test.mjs).
//
// Run: node --test tests/js/route_utils.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const sourcePath = join(here, "..", "..", "frontend", "static", "js", "route_utils.js");
const source = readFileSync(sourcePath, "utf8");

function loadWithLocation(pathname, basePath) {
    const sandbox = { window: { location: { pathname }, APP_BASE_PATH: basePath || "" } };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return sandbox.window;
}

// --- stripBasePath ---

test("stripBasePath: no base path leaves the raw path unchanged", () => {
    const w = loadWithLocation("/books/moby-dick");
    assert.equal(w.stripBasePath("/books/moby-dick", ""), "/books/moby-dick");
});

test("stripBasePath: strips a matching base path", () => {
    const w = loadWithLocation("/summrabook/books/moby-dick", "/summrabook");
    assert.equal(w.stripBasePath("/summrabook/books/moby-dick", "/summrabook"), "/books/moby-dick");
});

test("stripBasePath: base path equal to the whole path collapses to '/'", () => {
    const w = loadWithLocation("/summrabook", "/summrabook");
    assert.equal(w.stripBasePath("/summrabook", "/summrabook"), "/");
});

test("stripBasePath: a non-matching base path leaves the raw path unchanged", () => {
    const w = loadWithLocation("/books/moby-dick", "/other-prefix");
    assert.equal(w.stripBasePath("/books/moby-dick", "/other-prefix"), "/books/moby-dick");
});

// --- currentAppPath (reproduces the breadcrumb bug directly) ---

test("currentAppPath: root deployment (no base path) returns the raw pathname", () => {
    const w = loadWithLocation("/books/moby-dick", "");
    assert.equal(w.currentAppPath(), "/books/moby-dick");
});

test("currentAppPath: base-path deployment strips the prefix — this is the bug buildBreadcrumbs() had", () => {
    const w = loadWithLocation("/summrabook/books/moby-dick", "/summrabook");
    assert.equal(w.currentAppPath(), "/books/moby-dick");
});

// --- parseAppRoute ---

test("parseAppRoute: matches a book detail route", () => {
    const w = loadWithLocation("/books/moby-dick", "");
    const r = w.parseAppRoute("/books/moby-dick");
    assert.ok(r.bookMatch);
    assert.equal(r.bookMatch[1], "moby-dick");
    assert.equal(r.mediumMatch, null);
    assert.equal(r.chapterMatch, null);
});

test("parseAppRoute: matches a chapter route", () => {
    const w = loadWithLocation("", "");
    const r = w.parseAppRoute("/books/moby-dick/chapters/12");
    assert.ok(r.chapterMatch);
    assert.equal(r.chapterMatch[1], "moby-dick");
    assert.equal(r.chapterMatch[2], "12");
});

test("parseAppRoute: matches a category route", () => {
    const w = loadWithLocation("", "");
    const r = w.parseAppRoute("/categories/5");
    assert.ok(r.categoryMatch);
    assert.equal(r.categoryMatch[1], "5");
});

test("parseAppRoute: authorMatch allows slashes, matching the backend's <path:author_slug> converter", () => {
    const w = loadWithLocation("", "");
    const r = w.parseAppRoute("/authors/some/nested-slug");
    assert.ok(r.authorMatch, "authorMatch must accept slashes like the backend route does");
    assert.equal(r.authorMatch[1], "some/nested-slug");
});

test("parseAppRoute: exact-match routes (categories/books/discover/blog) set only their own flag", () => {
    const w = loadWithLocation("", "");
    assert.equal(w.parseAppRoute("/categories").categoriesMatch, true);
    assert.equal(w.parseAppRoute("/books").allBooksMatch, true);
    assert.equal(w.parseAppRoute("/discover").discoverMatch, true);
    assert.equal(w.parseAppRoute("/blog").blogMatch, true);
    assert.equal(w.parseAppRoute("/blog/some-post").blogPostMatch[1], "some-post");
});

// --- withBasePath / summraBasePath ---
// Moved here from app.js so components/BlogIndex.js and components/
// BlogPost.js (which load before app.js) can also call withBasePath() —
// see route_utils.js's module docstring.

test("summraBasePath: empty when APP_BASE_PATH is unset", () => {
    const w = loadWithLocation("/", "");
    assert.equal(w.summraBasePath(), "");
});

test("summraBasePath: reflects window.APP_BASE_PATH", () => {
    const w = loadWithLocation("/", "/summrabook");
    assert.equal(w.summraBasePath(), "/summrabook");
});

test("withBasePath: prefixes a root-relative path with the base path", () => {
    const w = loadWithLocation("/", "/summrabook");
    assert.equal(w.withBasePath("/api/blog"), "/summrabook/api/blog");
});

test("withBasePath: root deployment (no base path) leaves the path unchanged", () => {
    const w = loadWithLocation("/", "");
    assert.equal(w.withBasePath("/api/blog"), "/api/blog");
});

test("withBasePath: leaves absolute http(s)/protocol-relative URLs untouched", () => {
    const w = loadWithLocation("/", "/summrabook");
    assert.equal(w.withBasePath("https://example.com/x"), "https://example.com/x");
    assert.equal(w.withBasePath("http://example.com/x"), "http://example.com/x");
    assert.equal(w.withBasePath("//example.com/x"), "//example.com/x");
});

test("withBasePath: passes through falsy input unchanged", () => {
    const w = loadWithLocation("/", "/summrabook");
    assert.equal(w.withBasePath(""), "");
    assert.equal(w.withBasePath(null), null);
});
