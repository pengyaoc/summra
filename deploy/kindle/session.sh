#!/bin/sh
unset LD_LIBRARY_PATH
export DISPLAY=:0
BASE=/mnt/us/distill-fullscreen/native
STATE=/tmp/distill-native-fullscreen
WM=/mnt/us/koreader/wmctrl
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
case "${1:-launch}" in
  launch) APP_NAME=Distill; START_URL=https://pengyaochen.com/distill/ ;;
  --plainly) APP_NAME=Plainly; START_URL=https://pengyaochen.com/plainly/ ;;
  --current) APP_NAME=Browser; START_URL= ;;
  *) log 'Unknown launch mode; no changes made.'; exit 1 ;;
esac
MAX_SECONDS=${DISTILL_FULLSCREEN_SECONDS:-14400}
case "$MAX_SECONDS" in ''|*[!0-9]*) exit 1;; esac
[ "$MAX_SECONDS" -ge 10 ] && [ "$MAX_SECONDS" -le 14400 ] || exit 1
if ! mkdir "$STATE" 2>/dev/null; then
  log 'Session already starting or active; duplicate request ignored.'
  exit 0
fi
TOKEN="$$-$(cut -d . -f 1 /proc/uptime)"
echo "$TOKEN" > "$STATE/token"
echo $$ > "$STATE/pid"
log "Session starting pid=$$ mode=${1:-launch}"
WATCHER=
cleanup() {
  trap - EXIT HUP INT TERM
  "$BASE/restore.sh" "$TOKEN"
  if [ -n "$WATCHER" ]; then kill "$WATCHER" 2>/dev/null; wait "$WATCHER" 2>/dev/null; fi
  rm -f "$STATE/token" "$STATE/pid" "$STATE/window" "$STATE/original" "$STATE/full" "$STATE/stop"
  rmdir "$STATE" 2>/dev/null
}
trap cleanup EXIT HUP INT TERM
if [ "${1:-}" != '--current' ]; then
  # The scriptlet returns to Home after its shell exits. Starting Mesquite
  # before that handoff completes lets Home cancel the browser's LOAD.
  log 'Waiting for scriptlet-to-Home handoff.'
  sleep 2
  HANDOFF_COUNT=0
  HOME_SAMPLES=0
  while [ "$HANDOFF_COUNT" -lt 15 ]; do
    ACTIVE=$(lipc-get-prop com.lab126.appmgrd activeApp 2>/dev/null)
    if [ "$ACTIVE" = com.lab126.KPPMainApp ]; then
      HOME_SAMPLES=$((HOME_SAMPLES + 1))
      [ "$HOME_SAMPLES" -ge 3 ] && break
    else
      HOME_SAMPLES=0
    fi
    HANDOFF_COUNT=$((HANDOFF_COUNT + 1)); sleep 1
  done
  [ "$HOME_SAMPLES" -ge 3 ] || { log 'Home handoff did not settle; no browser launch attempted.'; exit 1; }
  POWER_STATE=$(lipc-get-prop com.lab126.powerd state 2>/dev/null)
  [ "$POWER_STATE" = active ] || { log 'Device is not awake; launch cancelled.'; exit 1; }
  log "Home stable; requesting $APP_NAME in stock browser."
  lipc-set-prop com.lab126.appmgrd start "app://com.lab126.browser/?view=$START_URL" || exit 1
fi
COUNT=0
while [ "$COUNT" -lt 40 ]; do
  ROW=$($WM -l | awk '$NF ~ /^L:A_N:application_/ && $NF ~ /_ID:com.lab126.browser$/ { print $1, $NF; exit }')
  ACTIVE=$(lipc-get-prop com.lab126.appmgrd activeApp 2>/dev/null)
  [ -n "$ROW" ] && [ "$ACTIVE" = com.lab126.browser ] && break
  COUNT=$((COUNT + 1)); sleep 1
done
[ "$COUNT" -lt 40 ] || { log 'Browser did not become active within 40 seconds.'; exit 1; }
WINDOW=${ROW%% *}
ORIGINAL=${ROW#* }
case "$ORIGINAL" in *_PC:TS_ID:com.lab126.browser) ;; *) log 'Unexpected browser title; no change made.'; exit 1;; esac
FULL=$(printf '%s' "$ORIGINAL" | sed 's/_PC:TS_/_PC:N_/')
printf '%s\n' "$WINDOW" > "$STATE/window"
printf '%s\n' "$ORIGINAL" > "$STATE/original"
printf '%s\n' "$FULL" > "$STATE/full"
# Independent of this process: power/sleep or the four-hour ceiling restores bars.
(
  LISTENER=
  trap '[ -z "$LISTENER" ] || kill "$LISTENER" 2>/dev/null; exit 0' HUP INT TERM
  lipc-wait-event -s "$MAX_SECONDS" com.lab126.powerd PowerButtonQuickPress,goingToScreenSaver >/dev/null 2>&1 &
  LISTENER=$!
  wait "$LISTENER"
  "$BASE/restore.sh" "$TOKEN"
) &
WATCHER=$!
sleep 1
[ ! -f "$STATE/stop" ] || exit 1
kill -0 "$WATCHER" 2>/dev/null || exit 1
"$WM" -i -r "$WINDOW" -T "$FULL" || exit 1
log "Fullscreen active window=$WINDOW; power/sleep restores bars."
while [ ! -f "$STATE/stop" ]; do
  ACTIVE=$(lipc-get-prop com.lab126.appmgrd activeApp 2>/dev/null)
  [ "$ACTIVE" = com.lab126.browser ] || break
  CURRENT=$($WM -l | awk -v id="$WINDOW" '$1 == id { print $NF; exit }')
  [ "$CURRENT" = "$FULL" ] || break
  sleep 1
done
