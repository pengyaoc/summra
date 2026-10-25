import sys

reloaded = False  # set when a test purged; conftest purges again on teardown


def purge_app_modules():
    """Drop the Plainly app and the shared modules it wires together from
    sys.modules, so the next import re-executes them as one unit.

    The routes hold references to shared.progress.routes / shared.auth, so a
    partial reload would leave later tests patching one copy while routes use
    another. plainly.scripts stays: those modules are standalone tools the app
    never imports, and tests hold references to them from import time.
    plainly.app_prod stays: it registers routes on the app singleton
    at import, and re-importing it after a request raises Flask's setup error.
    """
    global reloaded
    reloaded = True
    for name in [m for m in sys.modules
                 if ((m == 'plainly' or m.startswith('plainly.'))
                     and m != 'plainly.app_prod'
                     and not m.startswith('plainly.scripts'))
                 or m.startswith(('shared.progress', 'shared.auth'))]:
        sys.modules.pop(name, None)
    scripts = sys.modules.get('plainly.scripts')
    if scripts is not None:
        import plainly
        plainly.scripts = scripts  # the re-imported package must still expose it
