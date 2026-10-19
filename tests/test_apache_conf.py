"""deploy/apache/summra.conf moves old /summrabook links to the current prefix.

Production moved from pengyaochen.com/summrabook to pengyaochen.com/plainly
on 2026-10-18. Bookmarks, search results and shared links still point at
the old path, so the fragment must 301 them to the same page under the new
prefix.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / 'deploy/apache/summra.conf'


def _render(prefix):
    """Render the fragment the way deploy/install.sh does."""
    return subprocess.run(
        ['sed', f's#${{SUMMRA_PREFIX}}#{prefix}#g', str(CONF)],
        check=True, capture_output=True, text=True).stdout


def _legacy_redirect(rendered):
    m = re.search(r'^RedirectMatch 301 (\S+) (\S+)$', rendered, re.M)
    assert m, 'no 301 RedirectMatch for the old /summrabook prefix'
    return re.compile(m.group(1)), m.group(2)


def _target(rendered, path):
    pattern, dest = _legacy_redirect(rendered)
    m = pattern.match(path)
    return m.expand(dest.replace('$1', r'\1')) if m else None


def test_old_prefix_redirects_to_same_page_under_new_prefix():
    rendered = _render('/plainly')
    assert _target(rendered, '/summrabook/books/moby-dick') == '/plainly/books/moby-dick'
    assert _target(rendered, '/summrabook/') == '/plainly/'


def test_bare_old_prefix_redirects():
    assert _target(_render('/plainly'), '/summrabook') == '/plainly'


def test_lookalike_paths_are_not_redirected():
    rendered = _render('/plainly')
    assert _target(rendered, '/summrabooks/x') is None
    assert _target(rendered, '/plainly/books/moby-dick') is None
