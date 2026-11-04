#!/bin/sh
unset LD_LIBRARY_PATH
export DISPLAY=:0
BASE=/mnt/us/distill-fullscreen/native
STATE=/tmp/distill-native-fullscreen
WM=/mnt/us/koreader/wmctrl
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
# Input stays entirely in X11: input-only edge/corner windows intercept
# reserved gestures, with a page-area dismissal window only while bars show.
# Closing the X connection automatically removes every input window.
start_gestures() {
  /mnt/us/koreader/luajit - "$WINDOW" "$ORIGINAL" "$FULL" "$STATE" "${1:-run}" <<'LUA'
local window, original, full, state, mode = unpack(arg)
local function exists(path)
    local f = io.open(path, 'r'); if f then f:close(); return true end
    return false
end
local function controller(set_title, allow, edge, distance, height, corner)
    local c = { shown = false, drag = nil }
    function c:press(x, y, now)
        if x <= corner and y >= height - corner then
            self.drag = { toggle = true, x = x, y = y, at = now }; allow(false)
        elseif self.shown then
            self.drag = { dismiss = true }; allow(false)
        elseif y <= edge then
            self.drag = { x = x, y = y, at = now }; allow(false)
        else
            allow(true)
        end
    end
    function c:release(x, y, now)
        local d = self.drag; self.drag = nil
        if not d then return end
        if d.toggle and (now - d.at > 700 or math.abs(x - d.x) > 20 or math.abs(y - d.y) > 20) then
            return
        elseif d.toggle then
            self.shown = not self.shown; set_title(self.shown)
        elseif d.dismiss then
            self.shown = false; set_title(false)
        elseif now - d.at <= 1500 and y - d.y >= distance and
               math.abs(x - d.x) <= (y - d.y) / 2 then
            self.shown = true; set_title(true)
        end
    end
    return c
end
if mode == 'self-test' then
    local titles, replay = {}, {}
    local c = controller(function(v) titles[#titles+1] = v end,
        function(v) replay[#replay+1] = v end, 40, 80, 1448, 160)
    c:press(300, 300, 0); assert(replay[1] == true)
    c:release(300, 300, 100); assert(#titles == 0)
    c:press(300, 10, 100); c:release(310, 150, 400)
    assert(c.shown and titles[1] == true and replay[2] == false)
    c:press(500, 500, 500); assert(replay[3] == false)
    c:release(500, 500, 600); assert(not c.shown and titles[2] == false)
    c:press(300, 10, 700); c:release(500, 30, 900)
    assert(not c.shown and #titles == 2) -- horizontal swipe
    c:press(300, 10, 1000); c:release(300, 20, 1100)
    assert(not c.shown) -- edge tap
    c:press(300, 10, 1200); c:release(300, 150, 3000)
    assert(not c.shown) -- long hold
    c:press(300, 100, 3100); c:release(300, 400, 3300)
    assert(not c.shown and replay[#replay] == true) -- not from edge
    c:press(20, 1420, 3400); c:release(20, 1420, 3500)
    assert(c.shown and replay[#replay] == false)
    c:press(20, 1420, 3600); c:release(20, 1420, 3700)
    assert(not c.shown and replay[#replay] == false)
    c:press(20, 1420, 3800); c:release(120, 1320, 3900)
    assert(not c.shown) -- a corner drag is not a toggle
    c:press(20, 1420, 4000); c:release(20, 1420, 5000)
    assert(not c.shown) -- a corner hold is not a toggle
    c:press(107, 1367, 5100); c:release(96, 1378, 5200)
    assert(c.shown) -- physical tap outside the former 101px target
    c:press(140, 1320, 5300); c:release(143, 1322, 5400)
    assert(not c.shown) -- enlarged corner toggles off too
    c:press(180, 1350, 5500); c:release(180, 1350, 5600)
    assert(not c.shown and replay[#replay] == true) -- outside reserved corner
    print('PASS: ordinary taps replay; edge swipe reveals; dismissal consumes; corner toggles both ways; horizontal/short/slow/non-edge gestures rejected')
    return
end
local ffi = require('ffi')
ffi.cdef[[
typedef struct _XDisplay Display;
typedef unsigned long Window;
typedef struct { int type; unsigned long serial; int send_event; Display *display;
  Window window, root, subwindow; unsigned long time;
  int x, y, x_root, y_root; unsigned int state, button; int same_screen; } XButtonEvent;
typedef struct { unsigned long background_pixmap, background_pixel, border_pixmap, border_pixel;
  int bit_gravity, win_gravity, backing_store; unsigned long backing_planes, backing_pixel;
  int save_under; long event_mask, do_not_propagate_mask; int override_redirect;
  unsigned long colormap, cursor; } XSetWindowAttributes;
typedef struct { int x, y, width, height, border_width; Window sibling; int stack_mode; } XWindowChanges;
typedef union { int type; XButtonEvent button; long pad[24]; } XEvent;
Display *XOpenDisplay(const char *);
int XCloseDisplay(Display *);
Window XDefaultRootWindow(Display *);
Window XCreateWindow(Display *, Window, int, int, unsigned int, unsigned int,
  unsigned int, int, unsigned int, void *, unsigned long, XSetWindowAttributes *);
int XSelectInput(Display *, Window, long);
int XMapRaised(Display *, Window);
int XConfigureWindow(Display *, Window, unsigned int, XWindowChanges *);
int XUnmapWindow(Display *, Window);
int XMoveResizeWindow(Display *, Window, int, int, unsigned int, unsigned int);
int XDisplayWidth(Display *, int);
int XTranslateCoordinates(Display *, Window, Window, int, int, int *, int *, Window *);
int XPending(Display *);
int XNextEvent(Display *, XEvent *);
int XStoreName(Display *, Window, const char *);
unsigned long XInternAtom(Display *, const char *, int);
int XChangeProperty(Display *, Window, unsigned long, unsigned long, int, int, const unsigned char *, int);
int XGetWindowProperty(Display *, Window, unsigned long, long, long, int,
  unsigned long, unsigned long *, int *, unsigned long *, unsigned long *, unsigned char **);
int XFree(void *);
int XFlush(Display *);
int XSync(Display *, int);
int XDisplayHeight(Display *, int);
int XDefaultScreen(Display *);
int usleep(unsigned int);
int getpid(void);
typedef struct { int type; Display *display; unsigned long resourceid, serial; unsigned char error_code, request_code, minor_code; } XErrorEvent;
typedef int (*XErrorHandler)(Display *, void *);
XErrorHandler XSetErrorHandler(XErrorHandler);
]]
local x = ffi.load('X11')
local display = assert(x.XOpenDisplay(nil), 'Cannot open X display')
local win = assert(tonumber(window), 'Invalid browser window')
local failed = false
local handler = ffi.cast('XErrorHandler', function(_, error_event)
    local e = ffi.cast('XErrorEvent *', error_event)
    io.stderr:write('Native gesture X error ', tonumber(e.error_code), ' request ', tonumber(e.request_code), '\n')
    failed = true; return 0
end)
x.XSetErrorHandler(handler)
local height = x.XDisplayHeight(display, x.XDefaultScreen(display))
local width = x.XDisplayWidth(display, x.XDefaultScreen(display))
local root = x.XDefaultRootWindow(display)
local edge, corner = math.floor(height * .025), math.floor(height * .11)
local stack = ffi.new('XWindowChanges')
stack.sibling = win; stack.stack_mode = 0 -- Above browser, below native chrome/dialogs.
local function keep_above_browser(id)
    x.XConfigureWindow(display, id, 32 + 64, stack)
end
local attrs = ffi.new('XSetWindowAttributes')
attrs.override_redirect = 1
local function input_window(px, py, w, h)
    local id = x.XCreateWindow(display, root, px, py, w, h, 0, 0, 2, nil, 512, attrs)
    x.XSelectInput(display, id, 4 + 8 + 64)
    return id
end
local top = input_window(0, 0, width, edge)
local bottom = input_window(0, height - corner, corner, corner)
local dismiss = input_window(0, height - 1, width, 1)
local name_atom = x.XInternAtom(display, '_NET_WM_NAME', 0)
local utf8_atom = x.XInternAtom(display, 'UTF8_STRING', 0)
local function title(shown)
    io.stdout:write('Toolbar ', shown and 'shown' or 'hidden', '\n'); io.stdout:flush()
    local value = shown and original or full
    x.XChangeProperty(display, win, name_atom, utf8_atom, 8, 0, value, #value)
    x.XStoreName(display, win, value); x.XFlush(display)
end
local c = controller(title, function() end, edge, math.floor(height * .055), height, corner)
local mapped, sleeping = false, false
local function update_zones(shown)
    if exists(state .. '/suspended') then
        x.XUnmapWindow(display, top); x.XUnmapWindow(display, bottom); x.XUnmapWindow(display, dismiss)
        c.drag = nil; mapped = false; sleeping = true; x.XFlush(display)
        return
    elseif sleeping then
        x.XMapRaised(display, top); x.XMapRaised(display, bottom); sleeping = false
    end
    if shown then
        local px, py, child = ffi.new('int[1]'), ffi.new('int[1]'), ffi.new('Window[1]')
        if x.XTranslateCoordinates(display, win, root, 0, 0, px, py, child) == 0 then return end
        -- Wait until the window manager has actually placed the browser below
        -- the native bars. Never cover the bars, their menus or keyboard.
        if py[0] <= edge then return end
        x.XMoveResizeWindow(display, dismiss, 0, py[0], width, height - py[0])
        if not mapped then
            x.XUnmapWindow(display, top)
            x.XMapRaised(display, dismiss)
            x.XMapRaised(display, bottom)
            mapped = true
        end
    elseif mapped then
        x.XUnmapWindow(display, dismiss)
        x.XMapRaised(display, top)
        x.XMapRaised(display, bottom)
        mapped = false
    end
    keep_above_browser(top); keep_above_browser(dismiss); keep_above_browser(bottom)
    x.XFlush(display)
end
local pidfile = assert(io.open(state .. '/gesture-pid', 'w')); pidfile:write(tonumber(ffi.C.getpid()), '\n'); pidfile:close()
x.XMapRaised(display, top)
x.XMapRaised(display, bottom)
x.XSync(display, 0)
if failed then x.XCloseDisplay(display); error('Native input windows unavailable; leaving toolbar visible') end
local ready = assert(io.open(state .. '/gesture-ready', 'w')); ready:write('ready\n'); ready:close()
local event = ffi.new('XEvent[1]')
local tick = 0
while not failed and not exists(state .. '/stop') do
    while x.XPending(display) > 0 do
        x.XNextEvent(display, event)
        local e = event[0].button
        if event[0].type == 4 then
            if exists(state .. '/suspended') then c.drag = nil
            else
                io.stdout:write('Gesture press ', tonumber(e.x_root), ',', tonumber(e.y_root), ' bars=', tostring(c.shown), '\n'); io.stdout:flush()
                c:press(tonumber(e.x_root), tonumber(e.y_root), tonumber(e.time))
            end
        elseif event[0].type == 5 then
            c:release(tonumber(e.x_root), tonumber(e.y_root), tonumber(e.time))
            io.stdout:write('Gesture release ', tonumber(e.x_root), ',', tonumber(e.y_root), ' bars=', tostring(c.shown), '\n'); io.stdout:flush()
        end
    end
    tick = tick + 1
    if tick % 25 == 0 then
        local name = ffi.new('unsigned char *[1]')
        local actual, count, remaining = ffi.new('unsigned long[1]'), ffi.new('unsigned long[1]'), ffi.new('unsigned long[1]')
        local format = ffi.new('int[1]')
        local result = x.XGetWindowProperty(display, win, name_atom, 0, 1024, 0, utf8_atom,
            actual, format, count, remaining, name)
        if result ~= 0 or name[0] == nil then break end
        local current = ffi.string(name[0], count[0]); x.XFree(name[0])
        if current ~= original and current ~= full then
            io.stderr:write('Browser title ownership changed: ', current, '\n'); break
        end
        c.shown = current == original
        update_zones(c.shown)
    end
    ffi.C.usleep(20000)
end
x.XCloseDisplay(display)
handler:free()
io.stderr:write("Gesture helper stopped\n")
LUA
}
if [ "${1:-}" = '--gesture-self-test' ]; then
  start_gestures self-test
  exit $?
fi

case "${1:-launch}" in
  launch) APP_NAME=Distill; START_URL=https://pengyaochen.com/distill/ ;;
  --plainly) APP_NAME=Plainly; START_URL=https://pengyaochen.com/plainly/ ;;
  --current) APP_NAME=Browser; START_URL= ;;
  *) log 'Unknown launch mode; no changes made.'; exit 1 ;;
esac
MAX_SECONDS=${DISTILL_FULLSCREEN_SECONDS:-0}
case "$MAX_SECONDS" in ''|*[!0-9]*) exit 1;; esac
[ "$MAX_SECONDS" -eq 0 ] || { [ "$MAX_SECONDS" -ge 10 ] && [ "$MAX_SECONDS" -le 14400 ]; } || exit 1
if ! mkdir "$STATE" 2>/dev/null; then
  log 'Session already starting or active; duplicate request ignored.'
  exit 0
fi
TOKEN="$$-$(cut -d . -f 1 /proc/uptime)"
echo "$TOKEN" > "$STATE/token"
echo $$ > "$STATE/pid"
log "Session starting pid=$$ mode=${1:-launch}"
WATCHER=
GESTURES=
cleanup() {
  trap - EXIT HUP INT TERM
  "$BASE/restore.sh" "$TOKEN"
  HELPER_PID=$(cat "$STATE/gesture-pid" 2>/dev/null)
  case "$HELPER_PID" in ''|*[!0-9]*) ;; *) kill "$HELPER_PID" 2>/dev/null ;; esac
  if [ -n "$GESTURES" ]; then kill "$GESTURES" 2>/dev/null; wait "$GESTURES" 2>/dev/null; fi
  if [ -n "$WATCHER" ]; then kill "$WATCHER" 2>/dev/null; wait "$WATCHER" 2>/dev/null; fi
  rm -f "$STATE/token" "$STATE/pid" "$STATE/window" "$STATE/original" "$STATE/full" "$STATE/stop" "$STATE/gesture-ready" "$STATE/gesture-pid" "$STATE/suspended"
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
# Do not hide the escape controls until native input windows are confirmed.
start_gestures &
GESTURES=$!
COUNT=0
while [ ! -f "$STATE/gesture-ready" ] && [ "$COUNT" -lt 5 ]; do
  kill -0 "$GESTURES" 2>/dev/null || exit 1
  COUNT=$((COUNT + 1)); sleep 1
done
[ -f "$STATE/gesture-ready" ] || { log 'Native gesture setup failed; toolbar retained.'; exit 1; }
if [ "$MAX_SECONDS" -gt 0 ]; then
  (
    sleep "$MAX_SECONDS" & TIMER=$!
    trap 'kill "$TIMER" 2>/dev/null; wait "$TIMER" 2>/dev/null; exit 0' HUP INT TERM
    wait "$TIMER"
    "$BASE/restore.sh" "$TOKEN"
  ) &
  WATCHER=$!
fi
"$WM" -i -r "$WINDOW" -T "$FULL" || exit 1
log "Fullscreen active window=$WINDOW; top-edge swipe reveals toolbar; sleep preserves session."
WAS_ASLEEP=0
WAKE_GRACE=0
while [ ! -f "$STATE/stop" ]; do
  kill -0 "$GESTURES" 2>/dev/null || { log 'Gesture handler exited; restoring toolbar.'; break; }
  POWER_STATE=$(lipc-get-prop com.lab126.powerd state 2>/dev/null)
  if [ "$POWER_STATE" != active ]; then
    : > "$STATE/suspended"
    WAS_ASLEEP=1
    sleep 1
    continue
  fi
  if [ "$WAS_ASLEEP" -eq 1 ]; then
    WAS_ASLEEP=0; WAKE_GRACE=5
    "$WM" -i -r "$WINDOW" -T "$FULL" || break
    rm -f "$STATE/suspended"
    log 'Wake: fullscreen restored without navigation.'
  fi
  ACTIVE=$(lipc-get-prop com.lab126.appmgrd activeApp 2>/dev/null)
  if [ "$ACTIVE" != com.lab126.browser ]; then
    [ "$WAKE_GRACE" -gt 0 ] || break
    WAKE_GRACE=$((WAKE_GRACE - 1))
  else
    WAKE_GRACE=0
  fi
  CURRENT=$($WM -l | awk -v id="$WINDOW" '$1 == id { print $NF; exit }')
  [ "$CURRENT" = "$FULL" ] || [ "$CURRENT" = "$ORIGINAL" ] || break
  sleep 1
done
