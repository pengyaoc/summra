"""The JS (web reader) and Python (Kindle) block renderers must produce the
same markup for every block type under 'strict' inline. 'markdown' inline
needs marked, which exists only in the browser, so it is JS-only."""
import json
import subprocess
from pathlib import Path

from shared.reader import blocks

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests' / 'shared' / 'fixtures' / 'reader_blocks'

NODE_SCRIPT = r"""
import fs from 'node:fs';
const load = path => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path, 'utf8')).toString('base64'));
const {renderBlock} = await load('shared/static/js/blocks.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = input.blocks.map(block => renderBlock(block, {inline: 'strict', imageBase: input.imageBase}));
process.stdout.write(JSON.stringify(out));
"""


def _js_render(block_list, image_base):
    result = subprocess.run(
        ['node', '--input-type=module', '-e', NODE_SCRIPT], cwd=ROOT, check=True,
        input=json.dumps({'blocks': block_list, 'imageBase': image_base}), capture_output=True, text=True)
    return json.loads(result.stdout)


def test_js_and_python_render_identically():
    cases = json.loads((FIXTURES / 'blocks.json').read_text(encoding='utf-8'))
    block_list = [c['block'] for c in cases] + [{'type': 'callout', 'text': '*x*'}, {}]
    for image_base in ('', '/distill/books/x/', '/x"><script>&/'):
        js = _js_render(block_list, image_base)
        for block, rendered in zip(block_list, js, strict=True):
            tag, class_name, content = blocks.render_block(block, image_base=image_base)
            assert (rendered['tag'], rendered['className'], rendered['content']) == (tag, class_name, str(content)), block
