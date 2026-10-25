// reader_state.js on its own must give the shared reader everything it
// reaches through window.authModule, and must call the app's configured API.
//
// Run: node --test tests/js/reader_state.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const readerState = readFileSync(join(root, "shared", "static", "js", "reader_state.js"), "utf8");
const plainlyAuth = readFileSync(join(root, "plainly", "frontend", "static", "js", "auth.js"), "utf8");

function load(config, sources = [readerState], basePath = "") {
    const fetched = [];
    const sandbox = {
        window: { READER_CONFIG: config, APP_BASE_PATH: basePath },
        fetch: async url => {
            fetched.push(url);
            return { status: 200, ok: true, json: async () => ({ authenticated: false }) };
        },
    };
    vm.createContext(sandbox);
    for (const source of sources) vm.runInContext(source, sandbox);
    return { window: sandbox.window, fetched };
}

test("reader_state.js alone provides window.authModule for the shared reader", async () => {
    const { window, fetched } = load({ cache_db_name: "t", api_base: "/api" });
    const auth = window.authModule;
    for (const name of ["queueReaderMutation", "getReaderState", "getLibrary", "cacheReaderManifest",
        "getCachedReaderManifest", "cacheReaderSegment", "getCachedReaderSegment", "hintSeen",
        "markHintSeen", "currentUser", "initAuth"]) {
        assert.equal(typeof auth[name], "function", name);
    }
    await auth.initAuth();
    await auth.initAuth();
    assert.deepEqual(fetched, ["/api/auth/check"]);
});

test("Plainly's auth.js, loaded after reader_state.js, sets the authModule in force", () => {
    const { window } = load({ cache_db_name: "t", api_base: "/api" }, [readerState, plainlyAuth]);
    assert.equal(typeof window.authModule.trackPageChange, "function");
    assert.equal(window.authModule.queueReaderMutation, window.readerState.queueReaderMutation);
    assert.ok(window.authModule.initAuth.toString().includes("authInitializationPromise"));
});

test("progress, library and hint calls use READER_CONFIG.api_base", async () => {
    const custom = load({ cache_db_name: "t", api_base: "/reader-api" }, [readerState], "/distill");
    await custom.window.readerState.checkAuthStatus();
    assert.deepEqual(custom.fetched, ["/distill/reader-api/auth/check"]);

    const fallback = load({ cache_db_name: "t" }, [readerState], "/distill");
    await fallback.window.readerState.checkAuthStatus();
    assert.deepEqual(fallback.fetched, ["/distill/api/auth/check"]);
});
