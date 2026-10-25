// The shared reader platform is merged onto an app's class with
// Object.assign, so two mixins defining the same method would silently
// overwrite each other. Guards that, and that applyReaderPlatform only fills
// in its defaults where the host has no method of its own.
//
// Run: node --test tests/js/mixins_disjoint.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const sharedJs = join(here, "..", "..", "shared", "static", "js");
const plainlyJs = join(here, "..", "..", "plainly", "frontend", "static", "js");
const load = path => import(pathToFileURL(path).href);

test("platform mixins and Plainly's readerMixin define disjoint methods", async () => {
    const { readerUtilsMixin } = await load(join(sharedJs, "reader_utils.js"));
    const { paginationMixin } = await load(join(sharedJs, "pagination.js"));
    const { settingsMixin } = await load(join(sharedJs, "settings.js"));
    const { continuousReaderMixin } = await load(join(sharedJs, "continuous_reader.js"));
    const { readerMixin } = await load(join(plainlyJs, "reader.js"));
    const mixins = { readerUtilsMixin, paginationMixin, settingsMixin, continuousReaderMixin, readerMixin };
    const names = Object.keys(mixins);
    for (const name of names) assert.ok(Object.keys(mixins[name]).length > 0, `${name} is empty`);
    for (let i = 0; i < names.length; i += 1) {
        for (let j = i + 1; j < names.length; j += 1) {
            const overlap = Object.keys(mixins[names[i]]).filter(key => key in mixins[names[j]]);
            assert.deepEqual(overlap, [], `${names[i]} and ${names[j]} both define ${overlap.join(", ")}`);
        }
    }
});

test("applyReaderPlatform keeps the host's own methods and fills in missing defaults", async () => {
    const { applyReaderPlatform } = await load(join(sharedJs, "platform.js"));
    class Host {
        showOnlySections() { return "host"; }
    }
    applyReaderPlatform(Host);
    assert.equal(Host.prototype.showOnlySections(), "host");
    assert.equal(typeof Host.prototype.showContinuousReader, "function");
    assert.equal(typeof Host.prototype.initReaderPlatform, "function");

    class Bare {}
    applyReaderPlatform(Bare);
    assert.equal(Bare.prototype.showOnlySections(), undefined);
});

test("initReaderPlatform sets apiBase from config and a fresh pagination state", async () => {
    const { applyReaderPlatform, createPaginationState } = await load(join(sharedJs, "platform.js"));
    globalThis.window = { READER_CONFIG: { api_base: "/api" } };
    globalThis.withBasePath = path => `/distill${path}`;
    class Bare {}
    applyReaderPlatform(Bare);
    const app = new Bare();
    app.initReaderPlatform();
    assert.equal(app.apiBase, "/distill/api");
    assert.deepEqual(app.pagination, createPaginationState());
    assert.equal(app.pagination.currentViewMode, "original");
    assert.notEqual(createPaginationState(), createPaginationState());
});
