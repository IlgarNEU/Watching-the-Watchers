#!/bin/bash
# ==========================================
# Fire TV Control Script (via ADB)
# Equivalent of test.py for Vizio SmartCast
# ==========================================
#
# Setup:
#   1. Install ADB:  sudo apt install adb   (or brew install android-platform-tools)
#   2. On Fire TV:   Settings → My Fire TV → About → click 7 times to enable Developer Options
#   3. On Fire TV:   Settings → My Fire TV → Developer Options → ADB Debugging ON
#   4. First run:    ./firetv.sh connect     (accept prompt on TV screen)
#
# Usage:
#   ./firetv.sh <command> [args]

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────
FIRETV_IP="192.168.14.135" # e.g. 192.168.10.60
FIRETV_PORT=5555
FIRETV_MAC="28:73:F6:20:BA:95" # For Wake-on-LAN (find in Settings → My Fire TV → About → Network)

KEY_DELAY=0.5 # Seconds between key presses

# ─── ADB Helpers ──────────────────────────────────────────────────────────

adb_cmd() { adb -s "${FIRETV_IP}:${FIRETV_PORT}" "$@"; }
adb_shell() { adb_cmd shell "$@"; }
send_keyevent() {
  adb_shell input keyevent "$1"
  sleep "$KEY_DELAY"
}

send_wol() {
  python3 -c "
import socket
mac = bytes.fromhex('${1//:/}')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.sendto(b'\\xff'*6 + mac*16, ('192.168.14.255', 9))
s.close()
print('WoL sent to $1')
"
}

# ─── Keycodes ─────────────────────────────────────────────────────────────
# Standard Android keycodes used by Fire TV

key_home() { send_keyevent 3; }
key_back() { send_keyevent 4; }
key_up() { send_keyevent 19; }
key_down() { send_keyevent 20; }
key_left() { send_keyevent 21; }
key_right() { send_keyevent 22; }
key_ok() { send_keyevent 23; } # DPAD_CENTER = select
key_enter() { send_keyevent 66; }
key_menu() { send_keyevent 82; }
key_play() { send_keyevent 85; }
key_stop() { send_keyevent 86; }
key_rewind() { send_keyevent 89; }
key_ff() { send_keyevent 90; }
key_vol_up() { send_keyevent 24; }
key_vol_down() { send_keyevent 25; }
key_mute() { send_keyevent 164; }
key_power() { send_keyevent 26; }
key_sleep() { send_keyevent 223; }
key_wakeup() { send_keyevent 224; }
key_recent() { send_keyevent 187; }
key_search() { send_keyevent 84; }

# Number keys
key_0() { send_keyevent 7; }
key_1() { send_keyevent 8; }
key_2() { send_keyevent 9; }
key_3() { send_keyevent 10; }
key_4() { send_keyevent 11; }
key_5() { send_keyevent 12; }
key_6() { send_keyevent 13; }
key_7() { send_keyevent 14; }
key_8() { send_keyevent 15; }
key_9() { send_keyevent 16; }

# TV-specific keycodes (Fire TV Edition)
key_tv_input() { send_keyevent 178; } # May open input picker
key_channel_up() { send_keyevent 166; }
key_channel_down() { send_keyevent 167; }
key_guide() { send_keyevent 172; }
key_live_tv() { send_keyevent 173; } # May jump to live TV

# ─── Known App Packages ──────────────────────────────────────────────────

declare -A APPS=(
  [netflix]="com.netflix.ninja"
  [youtube]="com.amazon.firetv.youtube"
  [prime]="com.amazon.avod"
  [hulu]="com.hulu.plus"
  [disney]="com.disney.disneyplus"
  [tubi]="com.tubitv"
  [hbo]="com.hbo.hbomax"
  [peacock]="com.peacocktv.peacockandroid"
  [pluto]="tv.pluto.android"
  [plex]="com.plexapp.android"
  [spotify]="com.spotify.tv.android"
  [appletv]="com.apple.atve.amazon.appletv"
  [paramount]="com.cbs.ott"
  [freevee]="com.amazon.ftv.freevee"
  [silk]="com.amazon.cloud9"
  [livetv]="com.amazon.tv.livetv"
)

# ─── Commands ─────────────────────────────────────────────────────────────

cmd_connect() {
  echo "🔌 Connecting to ${FIRETV_IP}:${FIRETV_PORT}..."
  adb connect "${FIRETV_IP}:${FIRETV_PORT}"
  echo "✅ Accept the prompt on your TV if first time."
}

cmd_disconnect() { adb disconnect "${FIRETV_IP}:${FIRETV_PORT}"; }

cmd_on() {
  echo "📡 Waking Fire TV..."
  [[ "$FIRETV_MAC" != "XX:XX:XX:XX:XX:XX" ]] && send_wol "$FIRETV_MAC" && sleep 2
  adb connect "${FIRETV_IP}:${FIRETV_PORT}" 2>/dev/null || true
  send_keyevent 224 2>/dev/null || true # WAKEUP
  send_keyevent 3 2>/dev/null || true   # HOME
  echo "✅ Wake sent."
}

cmd_off() {
  echo "📴 Sleeping Fire TV..."
  send_keyevent 223 # SLEEP
  echo "✅ Sleep sent."
}

cmd_key() {
  local name="$1"
  local fn="key_${name}"
  if declare -f "$fn" >/dev/null 2>&1; then
    echo "🎮 Key: $name"
    $fn
  else
    echo "❌ Unknown key: $name"
    echo "   Available: home back up down left right ok enter menu play stop"
    echo "              rewind ff vol_up vol_down mute power sleep wakeup"
    echo "              0-9 tv_input channel_up channel_down guide live_tv"
    echo "              recent search"
    return 1
  fi
}

cmd_keys() {
  echo "Available keys:"
  echo "  [Navigation]   home back up down left right ok enter menu recent"
  echo "  [Power]        power sleep wakeup"
  echo "  [Volume]       vol_up vol_down mute"
  echo "  [Media]        play stop rewind ff"
  echo "  [TV/Live]      tv_input channel_up channel_down guide live_tv"
  echo "  [Numbers]      0 1 2 3 4 5 6 7 8 9"
  echo "  [Misc]         search"
}

cmd_launch() {
  local name="$1"
  local pkg="${APPS[$name]:-}"

  # Allow raw package names
  [[ -z "$pkg" && "$name" == *"."* ]] && pkg="$name"

  if [[ -z "$pkg" ]]; then
    echo "❌ Unknown app: $name"
    echo "   Known: ${!APPS[*]}"
    return 1
  fi

  echo "🚀 Launching: $name ($pkg)"
  # Try monkey first (most reliable for Fire TV)
  adb_shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 2>/dev/null && return 0
  # Fallback: am start with resolved activity
  adb_shell "am start \$(cmd package resolve-activity --brief $pkg 2>/dev/null | tail -1)" 2>/dev/null && return 0
  echo "⚠️  Launch failed for $pkg"
  return 1
}

cmd_close() {
  local name="$1"
  local pkg="${APPS[$name]:-$name}"
  echo "✖️  Stopping: $pkg"
  adb_shell am force-stop "$pkg"
}

cmd_apps() {
  echo "Known apps:"
  for name in $(echo "${!APPS[@]}" | tr ' ' '\n' | sort); do
    printf "  %-15s %s\n" "$name" "${APPS[$name]}"
  done
}

cmd_installed() {
  echo "Installed packages:"
  adb_shell pm list packages -3 | sed 's/package:/  /' | sort
}

cmd_current() {
  adb_shell "dumpsys window windows" | grep -E 'mCurrentFocus|mFocusedApp' | head -2
}

cmd_status() {
  echo "🔍 Fire TV Status:"
  if adb_cmd get-state 2>/dev/null | grep -q "device"; then
    echo "  ✅ ADB connected"
  else
    echo "  📴 Not connected — run: ./firetv.sh connect"
    return
  fi
  local wake
  wake=$(adb_shell "dumpsys power | grep mWakefulness" 2>/dev/null || echo "unknown")
  echo "  📺 $wake"
  echo "  📱 $(cmd_current 2>/dev/null || echo 'unknown')"
}

cmd_screenshot() {
  local f="${1:-screenshot.png}"
  adb_shell screencap -p /sdcard/ss.png
  adb_cmd pull /sdcard/ss.png "$f"
  adb_shell rm /sdcard/ss.png
  echo "📸 $f"
}

cmd_text() { adb_shell input text "${1// /%s}"; }

cmd_shell() { adb_shell "$@"; }

# Send a raw keyevent number
cmd_keyevent() {
  echo "Sending keyevent $1"
  send_keyevent "$1"
}

# ─── Test: find which keycodes work for inputs on YOUR model ──────────────

cmd_test_inputs() {
  cat <<'EOF'
Testing input-related keycodes on your Fire TV Edition.
Watch the TV screen after each — note which one opens an input picker.

Press Enter to start (or Ctrl+C to cancel)...
EOF
  read -r

  echo "--- keyevent 178 (TV_INPUT) ---"
  send_keyevent 178
  sleep 3
  send_keyevent 4 # back to dismiss

  echo "--- keyevent 170 (TV_INPUT_HDMI_1) ---"
  send_keyevent 170
  sleep 3
  send_keyevent 4

  echo "--- keyevent 171 (TV_INPUT_HDMI_2) ---"
  send_keyevent 171
  sleep 3
  send_keyevent 4

  echo "--- keyevent 176 (TV_INPUT_COMPONENT_1) ---"
  send_keyevent 176
  sleep 3
  send_keyevent 4

  echo "--- Trying Live TV app ---"
  adb_shell monkey -p com.amazon.tv.livetv -c android.intent.category.LAUNCHER 1 2>/dev/null
  sleep 3
  send_keyevent 4

  echo "--- Trying input preference activity ---"
  adb_shell am start -n com.amazon.tv.inputpreference/.InputPickerActivity 2>/dev/null
  sleep 3
  send_keyevent 4

  echo "--- Trying settings TV inputs ---"
  adb_shell am start -a android.settings.TV_INPUT_SETTINGS 2>/dev/null
  sleep 3
  send_keyevent 4

  echo ""
  echo "Done. Which one(s) worked? Update the input functions in this script."
}

# ─── CLI ──────────────────────────────────────────────────────────────────

case "${1:-}" in
connect) cmd_connect ;;
disconnect) cmd_disconnect ;;
status) cmd_status ;;
on) cmd_on ;;
off) cmd_off ;;
key) cmd_key "${2:?key name required}" ;;
keys) cmd_keys ;;
keyevent) cmd_keyevent "${2:?keycode number required}" ;;
launch) cmd_launch "${2:?app name required}" ;;
close) cmd_close "${2:?app name required}" ;;
apps) cmd_apps ;;
installed) cmd_installed ;;
current) cmd_current ;;
screenshot) cmd_screenshot "${2:-screenshot.png}" ;;
text) cmd_text "${2:?text required}" ;;
shell)
  shift
  cmd_shell "$@"
  ;;
test-inputs) cmd_test_inputs ;;
*)
  cat <<'EOF'
Fire TV Edition Control (ADB)
══════════════════════════════
  connect / disconnect       ADB connection
  on / off                   Wake / Sleep
  status                     Connection + screen state
  key <name>                 Send key (run 'keys' for list)
  keyevent <code>            Send raw Android keyevent number
  keys                       List available key names
  launch <app>               Launch app (run 'apps' for list)
  close <app>                Force stop app
  apps / installed / current App info
  screenshot [file]          Take screenshot
  text "hello"               Type text
  shell <cmd>                Raw ADB shell
  test-inputs                Find which keycodes switch inputs
EOF
  ;;
esac
