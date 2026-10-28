# Kindle fullscreen shortcuts

These jailbreak launcher scripts open the existing stock Kindle Web Browser in
an app-style window. They do not install a browser engine or a conventional PWA.
This directory is the version-controlled source of truth for both apps.

## Contents

- `distill.sh` / `plainly.sh`: Home library entries, with embedded PNG book covers.
- `distill-restore-toolbar.sh`: **Restore Distill Toolbar**, shared by both apps.
- `session.sh`: shared runtime and allowlisted site URLs; default Distill,
  `--plainly` for Plainly, `--current` for the currently open browser.
- `restore.sh`: restores the recorded browser title only if it still matches
  the fullscreen title owned by this session.
- `*-cover.png` and available SVG originals: 250 × 391 monochrome covers.
  Distill uses its drop mark; Plainly uses its book-and-sparkle mark.

The PNG is embedded in each shortcut's single `# Icon: data:image/png;base64,...`
metadata line. Update that line when changing a cover. Do not add SSH keys,
known-host files, login cookies, device logs, or old Chromium disk images here.

## Prerequisites and installation

Verified on jailbroken Paperwhite 3, firmware 5.16.2.1.1, Linux 3.0.35,
1072 × 1448 portrait display, SH_Integration Home scriptlets and KOReader's
`/mnt/us/koreader/wmctrl`. Other firmware/device combinations are unverified.
Back up existing installed versions before replacing them.

With Kindle connected as USB storage, substitute its actual mount point:

```sh
KINDLE_VOLUME=/Volumes/Kindle
mkdir -p "$KINDLE_VOLUME/distill-fullscreen/native"
cp deploy/kindle/*.sh deploy/kindle/*-cover.* "$KINDLE_VOLUME/distill-fullscreen/native/"
cp deploy/kindle/README.md "$KINDLE_VOLUME/distill-fullscreen/README.md"
cp deploy/kindle/distill.sh deploy/kindle/plainly.sh \
   deploy/kindle/distill-restore-toolbar.sh "$KINDLE_VOLUME/documents/"
chmod +x "$KINDLE_VOLUME/distill-fullscreen/native/"*.sh \
  "$KINDLE_VOLUME/documents/distill.sh" "$KINDLE_VOLUME/documents/plainly.sh" \
  "$KINDLE_VOLUME/documents/distill-restore-toolbar.sh"
```

Safely eject, unplug USB, enable Wi-Fi, then tap **Distill Fullscreen** or
**Plainly Fullscreen** once. Allow 8–10 seconds for the Home handoff and browser
startup. Home indexing may briefly hide a shortcut after its cover changes.
USB storage and a running SSH session must not access the filesystem together.

The existing device README has historical experiment records. Preserve those
before replacing it. The old Mac working copy was
`~/.local/share/distill-kindle/native-fullscreen/`; edit this repo going forward
and explicitly reinstall changed files. Git pushes do not update the Kindle.

## Operation and recovery

The shared state directory `/tmp/distill-native-fullscreen/` prevents two apps
from controlling the same native browser window. A normal appmgr launch waits
for stable Home samples so scriptlet exit cannot cancel the browser startup.
It then records the exact browser window/title and changes `PC:TS` to `PC:N`.
This reclaims the native URL and status bar area without changing browser files.

Power/sleep events, leaving the browser, process exit, the four-hour ceiling,
or **Restore Distill Toolbar** request restoration. Normal sleep stays enabled;
there is no autostart or sleep-prevention setting. The restore shortcut serves
both apps despite its existing Distill name. Log:
`/mnt/us/distill-fullscreen/native/session.log`.

For a short supervised recovery check, set `DISTILL_FULLSCREEN_SECONDS=30`
(range 10–14400) when invoking `session.sh`. Default is 14400 seconds. Run
`sh -n deploy/kindle/*.sh` individually before installing script edits.
Actual Home launches, covers, manual restore and a shortened timeout were
verified. A physical power-button event was not exercised during verification.
A forced kill or system failure can leave stale RAM state; inspect processes
and the recorded window before removing state or relaunching.

Do not use direct `com.lab126.browser go` LIPC calls: these crashed Mesquite in
trials. Use the normal appmgr URL launch. Earlier custom-Mesquite and
Alpine/Chromium trials are retired; their scripts remain in the Kindle's
`/mnt/us/distill-fullscreen/archive-2026-10-27/`, outside this source directory.
Their large images/logs are not needed by these shortcuts.

## Sign-in and reader code

On Kindle e-readers, choose **Sign in**, scan the QR code with a phone, complete
Google sign-in, compare the code and approve your Kindle. The Kindle checks
every ten seconds without JavaScript. Sessions last up to 30 days; phone-only
`/distill/pair/devices` and `/plainly/pair/devices` revoke them. Plainly public
reading remains available before signing in. Each app pairs independently;
Distill's private library never becomes public.

Shared server code: `shared/auth/device_pairing.py`; shared pairing screen:
`shared/templates/shared/kindle/pairing.html`. Reader JS/CSS and templates live
under `shared/static/` and `shared/templates/shared/kindle/`. Native fullscreen
viewport handling is in `shared/static/js/kindle.js`, not the launchers.
