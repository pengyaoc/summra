// Unit tests for base_path.js — summraBasePath()/withBasePath(), moved out of
// route_utils.js so the shared reader platform can use them in any app.
//
// Loads the exact same file the browser loads, inside a stub-window context
// (same pattern as route_utils.test.mjs).
//
// Run: node --test tests/js/base_path.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const sourcePath = join(here, "..", "..", "shared", "static", "js", "base_path.js");
const source = readFileSync(sourcePath, "utf8");

function loadWithLocation(pathname, basePath) {
    const sandbox = { window: { location: { pathname }, APP_BASE_PATH: basePath || "" } };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return sandbox.window;
}

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
