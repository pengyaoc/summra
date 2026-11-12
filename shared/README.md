# Shared platform

This is the code both apps run on: [Plainly](../plainly/README.md) and [Distill](../distill/README.md). An app brings its content database, its pages and a few small descriptions of itself. Everything below comes from here.

**Rule:** nothing in `shared/` imports `plainly` or `distill`. Apps pass their specifics in. `tests/shared/` holds the platform tests, and any change here must keep both apps' suites (pytest and e2e) green.

| Package | What it does | How an app plugs in |
|---|---|---|
| `reader/` | The continuous reader: paragraph index (`index.py`), reader API (manifest, segments, marker recovery), the block vocabulary rendered in Python for Kindle (`blocks.py`, kept in step with `static/js/blocks.js`), and the mode registry | The app builds one `ReaderConfig` (`<app>/reader_config.py`) and calls `platform.py` |
| `progress/` | Reading-progress API: saved place and chapter completion | Registered by the app factory |
| `kindle/` | Kindle browser detection, page dispatch and progress recording | The app adds its own Kindle pages using `templates/shared/kindle/` |
| `audio/` | Chapter audio: recording on the owner's Mac (`make_audio.py`, macOS voices), storage, and the playback API | The app supplies `<app>/audio_app.py` and an `audio_spoken_units` hook |
| `auth/` | `pchauth`: identity from the trusted `X-Remote-Email` header that Apache sets after Google sign-in; user and progress models | The app picks an auth mode and, if it needs one, an allow-list |
| `web.py` | Reverse-proxy prefix, gzip, content-hash asset versioning, shared UI install | Called from the app factory |
| `media.py` | Private content-addressed media files kept beside the content DB | Used by Distill's images and both apps' audio |
| `static/`, `templates/shared/` | Reader CSS, JS and fonts; reader and Kindle templates | Each app symlinks `static/shared → shared/static` |

The architecture and the reasons behind it are in [`docs/shared/ERD.md`](../docs/shared/ERD.md): see "Repository layout" and "Shared audio player". Product behaviour is in [`docs/shared/PRD.md`](../docs/shared/PRD.md).
