import sys


def purge_app_modules():
    """Drop the Plainly app and the shared modules it wires together from
    sys.modules, so the next import re-executes them as one unit.

    The routes hold references to shared.progress.routes / shared.auth, so a
    partial reload would leave later tests patching one copy while routes use
    another. plainly.app_prod stays: it registers routes on the app singleton
    at import, and re-importing it after a request raises Flask's setup error.
    """
    for name in [m for m in sys.modules
                 if ((m == 'plainly' or m.startswith('plainly.')) and m != 'plainly.app_prod')
                 or m.startswith(('shared.progress', 'shared.auth'))]:
        sys.modules.pop(name, None)
