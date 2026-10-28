#!/bin/sh
unset LD_LIBRARY_PATH
export DISPLAY=:0
STATE=/tmp/distill-native-fullscreen
WM=/mnt/us/koreader/wmctrl
[ -d "$STATE" ] || exit 0
TOKEN=$(cat "$STATE/token" 2>/dev/null) || exit 1
[ -z "${1:-}" ] || [ "$1" = "$TOKEN" ] || exit 0
WINDOW=$(cat "$STATE/window" 2>/dev/null) || exit 1
ORIGINAL=$(cat "$STATE/original" 2>/dev/null) || exit 1
FULL=$(cat "$STATE/full" 2>/dev/null) || exit 1
case "$WINDOW" in 0x*[!0-9a-fA-Fx]*) exit 1;; 0x*) ;; *) exit 1;; esac
case "$ORIGINAL" in L:A_N:application_PC:TS_ID:com.lab126.browser|L:A_N:application_*_PC:TS_ID:com.lab126.browser) ;; *) exit 1;; esac
CURRENT=$($WM -l | awk -v id="$WINDOW" '$1 == id { print $NF; exit }')
if [ "$CURRENT" = "$FULL" ]; then
  "$WM" -i -r "$WINDOW" -T "$ORIGINAL" || exit 1
fi
: > "$STATE/stop"
