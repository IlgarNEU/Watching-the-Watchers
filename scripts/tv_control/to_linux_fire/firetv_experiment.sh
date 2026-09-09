#!/bin/bash
# ==========================================
# Fire TV Experiment Runner
# ==========================================
# Automates 7 scenarios with power cycling,
# CSV logging, and PCAP fetching.
#
# Requires: firetv.sh in the same directory
#
# Usage:
#   ./firetv_experiment.sh run [N]   Run all 7 scenarios N times (default 1)
#   ./firetv_experiment.sh fetch     Fetch PCAPs from server
#   ./firetv_experiment.sh status    Show experiment counts

set -uo pipefail

# ==========================================
# Configuration
# ==========================================
FIRETV="./firetv.sh"

KEY_DELAY=2           # Seconds between button presses
BOOT_DELAY=25         # Initial wait after wake
MAX_BOOT_RETRIES=5    # WoL/ADB retries if TV doesn't come up
BOOT_POLL_INTERVAL=10 # Seconds between reachability checks
RUN_CMD_RETRIES=3     # Retries per command on failure
RUN_CMD_RETRY_WAIT=5  # Seconds between retries
SCENARIO_DURATION=30 # Seconds per scenario (2400 = 40 min)
POWER_OFF_WAIT=30    # Seconds after sleep before next wake
APP_LAUNCH_WAIT=20    # Seconds to let an app fully load

CSV_FILE="Experiment_times.csv"
LOG_FILE="experiment_debug.log"

# PCAP server
PCAP_USER="het"
PCAP_HOST="129.10.227.207"
PCAP_BASE="/traffic/by-mac"
FIRETV_MAC="28:73:F6:20:BA:95" # For Wake-on-LAN (find in Settings → My Fire TV → About → Network)
TV_NAME="FireTV"
PCAP_LOCAL="./data"

# ADB target (must match firetv.sh)
FIRETV_IP="192.168.14.135" # e.g. 192.168.10.60
FIRETV_PORT=5555

# Repetition counter (FAST → FAST2 → FAST3...)
declare -A REP_COUNT

# ==========================================
# Connectivity & Recovery
# ==========================================

tv_is_reachable() {
  # Check ADB connection state
  local state
  state=$(adb -s "${FIRETV_IP}:${FIRETV_PORT}" get-state 2>/dev/null || echo "offline")
  [[ "$state" == "device" ]]
}

adb_reconnect() {
  log "  Reconnecting ADB..."
  adb connect "${FIRETV_IP}:${FIRETV_PORT}" 2>/dev/null || true
  sleep 2
}

wait_for_tv() {
  local attempt=1
  log "  Waiting for Fire TV to become reachable..."
  sleep $BOOT_DELAY

  # Try reconnecting first
  adb_reconnect

  while ! tv_is_reachable; do
    if [[ $attempt -ge $MAX_BOOT_RETRIES ]]; then
      log "  ❌ Fire TV unreachable after $MAX_BOOT_RETRIES retries — last WoL + reconnect..."
      "$FIRETV" on 2>/dev/null || true
      sleep $BOOT_DELAY
      adb_reconnect
      if ! tv_is_reachable; then
        log "  ❌ FATAL: Fire TV not reachable. Skipping remaining commands."
        return 1
      fi
      return 0
    fi
    log "  Not reachable (attempt $attempt/$MAX_BOOT_RETRIES) — WoL + reconnect..."
    "$FIRETV" on 2>/dev/null || true
    sleep $BOOT_POLL_INTERVAL
    adb_reconnect
    ((attempt++))
  done
  log "  ✅ Fire TV is reachable."
  return 0
}

# ==========================================
# Helper Functions
# ==========================================

run_cmd() {
  local attempt=1
  while [[ $attempt -le $RUN_CMD_RETRIES ]]; do
    echo "  -> $FIRETV $*"
    local output
    output=$("$FIRETV" "$@" 2>&1) || true
    echo "$output"

    # Check for ADB/network errors
    if echo "$output" | grep -qiE "error|refused|offline|closed|unable to connect|no route|timed out|cannot connect"; then
      log "  ⚠️  Command failed (attempt $attempt/$RUN_CMD_RETRIES): $*"
      if [[ $attempt -lt $RUN_CMD_RETRIES ]]; then
        if ! tv_is_reachable; then
          log "  TV unreachable — attempting recovery..."
          adb_reconnect
          if ! tv_is_reachable; then
            wait_for_tv || return 1
          fi
        else
          sleep $RUN_CMD_RETRY_WAIT
        fi
      fi
      ((attempt++))
    else
      sleep $KEY_DELAY
      return 0
    fi
  done
  log "  ❌ Command failed after $RUN_CMD_RETRIES retries: $*"
  sleep $KEY_DELAY
  return 1
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

init_csv() {
  if [[ ! -f "$CSV_FILE" ]]; then
    echo "date,start_time,end_time,action_name,subprocesses,subprocesses_start,subprocesses_end,subprocesses_exist" >"$CSV_FILE"
  fi
}

get_action_name() {
  local base="$1"
  REP_COUNT[$base]=$((${REP_COUNT[$base]:-0} + 1))
  local rep=${REP_COUNT[$base]}
  if [[ $rep -eq 1 ]]; then echo "$base"; else echo "${base}${rep}"; fi
}

go_home() {
  log "  Returning to Home screen..."
  run_cmd key home
  sleep 2
}

powercycle() {
  log "--- Power Cycling ---"
  run_cmd off
  log "  Waiting ${POWER_OFF_WAIT}s..."
  sleep $POWER_OFF_WAIT
  run_cmd on
  wait_for_tv
}

# ==========================================
# Core: run one scenario, log it, powercycle
# ==========================================

run_scenario() {
  local label="$1"
  local step="$2"

  local action_name
  action_name="$(get_action_name "$label")"

  local date_str start_time end_time
  date_str="$(date '+%Y-%m-%d')"
  start_time="$(date '+%H:%M:%S')"

  log "${step} ${action_name}: running for $((SCENARIO_DURATION / 60)) min..."
  sleep $SCENARIO_DURATION

  end_time="$(date '+%H:%M:%S')"
  echo "${date_str},${start_time},${end_time},${action_name},,,,no" >>"$CSV_FILE"
  log "  📝 ${action_name} → ${start_time} to ${end_time}"

  exit_app
  powercycle
}

# ==========================================
# Ctrl+C safety
# ==========================================
trap 'echo ""; log "⚠️ Interrupted — sleeping Fire TV..."; "$FIRETV" off 2>/dev/null; exit 1' SIGINT SIGTERM

# ==========================================
# Navigation: base position from Home screen
# ==========================================

base_position() {
  log "  Navigating to base position..."
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key up
  run_cmd key down
  run_cmd key back
}

exit_app() {
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
  run_cmd key back
}

# ==========================================
# Scenario Launchers
# ==========================================

launch_fast() {
  log "  Launching FAST..."
  base_position
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key ok
}

launch_netflix() {
  log "  Launching Netflix..."
  run_cmd launch netflix
  sleep $APP_LAUNCH_WAIT
  sleep 10
  run_cmd key left
  sleep 360
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
}

launch_tubi() {
  log "  Launching Tubi..."
  base_position
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  run_cmd key ok
  sleep $APP_LAUNCH_WAIT
  run_cmd key ok
  run_cmd key ok
}

launch_youtube() {
  log "  Launching YouTube..."
  base_position
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  run_cmd key ok
  run_cmd key back
  run_cmd key up
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key right
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key ok
  run_cmd key right
  run_cmd key ok
}

launch_antenna_random() {
  log "  Launching Antenna (random)..."
  base_position
  run_cmd key right
  run_cmd key down
  run_cmd key ok
  run_cmd key ok
}

launch_antenna_14_1() {
  log "  Launching Antenna 14.1..."
  base_position
  run_cmd key right
  run_cmd key down
  run_cmd key ok
  run_cmd key down
  run_cmd key ok
}

launch_hdmi() {
  log "  Switching to HDMI..."
  base_position
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key down
  run_cmd key ok
}

# ==========================================
# Run all 7 scenarios
# ==========================================

run_all() {
  # [1/7] FAST
  echo ""
  echo "━━━ [1/7] FAST (Amazon Free Channels) ━━━"
  go_home
  launch_fast
  run_scenario "FAST" "[1/7]"

  # [2/7] Netflix
  echo ""
  echo "━━━ [2/7] Netflix ━━━"
  go_home
  launch_netflix
  run_scenario "Netflix" "[2/7]"

  # [3/7] Tubi
  echo ""
  echo "━━━ [3/7] Tubi ━━━"
  go_home
  launch_tubi
  run_scenario "Tubi" "[3/7]"

  # [4/7] YouTube
  echo ""
  echo "━━━ [4/7] YouTube ━━━"
  go_home
  launch_youtube
  run_scenario "Youtube" "[4/7]"

  # [5/7] Antenna (random)
  echo ""
  echo "━━━ [5/7] Antenna (random) ━━━"
  go_home
  launch_antenna_random
  run_scenario "Antenna" "[5/7]"

  # [6/7] Antenna 14.1
  echo ""
  echo "━━━ [6/7] Antenna 14.1 ━━━"
  go_home
  launch_antenna_14_1
  run_scenario "Antenna_14.1" "[6/7]"

  # [7/7] HDMI
  echo ""
  echo "━━━ [7/7] HDMI ━━━"
  go_home
  launch_hdmi
  run_scenario "HDMI" "[7/7]"
}

toggle_acr_off() {
  base_position
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  run_cmd key down
  run_cmd key ok
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_cmd off
}


toggle_acr_on() {
  base_position
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  run_cmd key down
  run_cmd key ok
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_cmd key ok
  run_cmd off
}

# ==========================================
# PCAP Fetching
# ==========================================

fetch_pcaps() {
  log "📦 Fetching PCAPs..."
  local dates
  dates=$(tail -n +2 "$CSV_FILE" | cut -d',' -f1 | sort -u)

  for date in $dates; do
    local dir="${PCAP_LOCAL}/${date}/${TV_NAME}/_raw_pcaps"
    mkdir -p "$dir"
    log "  rsync ${date}..."
    rsync -avzP --ignore-existing \
      "${PCAP_USER}@${PCAP_HOST}:${PCAP_BASE}/${TV_MAC}/unctrl/${date}*" \
      "${dir}/"

    while IFS=',' read -r d st et action _; do
      if [[ "$d" == "$date" && -n "$action" ]]; then
        mkdir -p "${PCAP_LOCAL}/${date}/${TV_NAME}/${action}/pcaps"
      fi
    done < <(tail -n +2 "$CSV_FILE")
  done
  log "✅ Done. Move PCAPs from _raw_pcaps/ into scenario dirs by timestamp."
}

# ==========================================
# Main
# ==========================================

init_csv

case "${1:-run}" in
run)
  REPS="${2:-1}"
  log "═══════════════════════════════════════════════"
  log "Fire TV Experiment: ${REPS} rep(s), $((SCENARIO_DURATION / 60)) min/scenario"
  log "═══════════════════════════════════════════════"

  # Initial boot
  run_cmd on
  wait_for_tv

  for i in $(seq 1 "$REPS"); do
    log "══════ REPETITION $i / $REPS ══════"
    toggle_acr_on
    run_all
    log "=============== one set done ============="
    toggle_acr_off
    log "============= ACR toggled ================="
    run_all
  done
  log "🎉 All done! CSV: $CSV_FILE"
  ;;
fetch)
  fetch_pcaps
  ;;
status)
  echo "Logged: $(($(wc -l <"$CSV_FILE") - 1)) experiments"
  echo ""
  tail -n +2 "$CSV_FILE" | cut -d',' -f4 | sort | uniq -c | sort -rn
  ;;
*)
  cat <<'EOF'
Fire TV Experiment Runner
═════════════════════════
  run [N]     Run all 7 scenarios N times (default 1)
  fetch       Fetch PCAPs from server
  status      Show experiment counts

Scenarios:
  1. FAST          Amazon free channels (Live TV)
  2. Netflix       Netflix app
  3. Tubi          Tubi app
  4. YouTube       YouTube app
  5. Antenna       Random OTA channel
  6. Antenna 14.1  Specific OTA sub-channel
  7. HDMI          HDMI input
EOF
  ;;
esac
