// The shared block renderer (shared/static/js/blocks.js): one render
// vocabulary for both apps. Plainly's readerMixin.classifyUnit turns a text
// unit into a block; blocksMixin renders it. The Plainly golden was recorded
// from the live reader before the renderer existed.
//
// Run: node --test tests/js/blocks.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const fixtures = join(root, "tests", "shared", "fixtures", "reader_blocks");
const readJson = name => JSON.parse(readFileSync(join(fixtures, name), "utf8"));
const load = path => import(pathToFileURL(path).href);
const { renderBlock, formatInline, escapeText, blocksMixin } = await load(join(root, "shared", "static", "js", "blocks.js"));
const { readerUtilsMixin } = await load(join(root, "shared", "static", "js", "reader_utils.js"));
const { readerMixin } = await load(join(root, "plainly", "frontend", "static", "js", "reader.js"));

const STRICT = { inline: "strict", imageBase: "" };

test("renders_each_type", () => {
    for (const { name, block, strict } of readJson("blocks.json")) {
        assert.deepEqual(renderBlock(block, STRICT), strict, name);
    }
});

test("unknown_type_falls_back_to_p", () => {
    assert.deepEqual(renderBlock({ type: "callout", text: "Hi *there*" }, STRICT),
        { tag: "p", className: "", content: "Hi <em>there</em>" });
    assert.deepEqual(renderBlock({}, STRICT), { tag: "p", className: "", content: "" });
});

test("strict_inline_escapes_then_marks_up", () => {
    assert.equal(formatInline("<b>x</b> & **y** *z* _w_", "strict"),
        "&lt;b&gt;x&lt;/b&gt; &amp; <strong>y</strong> <em>z</em> _w_");
    assert.equal(formatInline("**<i>**", "strict"), "<strong>&lt;i&gt;</strong>");
    assert.equal(escapeText("a b <&>\"'"), "a&nbsp;b &lt;&amp;&gt;\"'");
});

test("image_base_prefixes_src", () => {
    const block = { type: "image", src: "images/a.png" };
    assert.equal(renderBlock(block, { inline: "strict", imageBase: "/distill/books/x/" }).content,
        '<img src="/distill/books/x/images/a.png" alt="">');
    assert.equal(renderBlock(block, STRICT).content, '<img src="images/a.png" alt="">');
});

test("plainly_classifier_matches_golden_without_marked", () => {
    assert.equal(typeof globalThis.marked, "undefined");
    globalThis.window = { READER_CONFIG: { inline: "markdown", image_base: "" } };
    const app = { ...readerUtilsMixin, ...readerMixin, ...blocksMixin };
    const units = readJson("plainly_units.json");
    const golden = readJson("plainly_golden.json").fallback;
    assert.equal(golden.length, units.length);
    units.forEach((unit, i) => assert.deepEqual(app.continuousReaderBlock(unit), golden[i], `unit ${i}: ${unit.slice(0, 40)}`));
});

test("blocksMixin and Plainly's readerMixin define disjoint methods", () => {
    const overlap = Object.keys(blocksMixin).filter(key => key in readerMixin);
    assert.deepEqual(overlap, []);
    assert.equal(typeof readerMixin.classifyUnit, "function");
});
