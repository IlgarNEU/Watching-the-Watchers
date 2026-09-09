#!/bin/bash

# ==========================================
# Configuration Variables
# ==========================================
SCRIPT="test.py"
KEY_DELAY=3           # Seconds between button presses
BOOT_DELAY=20         # Seconds for initial TV boot wait
MAX_BOOT_RETRIES=5    # Max WoL retries if TV doesn't come up
BOOT_POLL_INTERVAL=10 # Seconds between reachability checks
RUN_CMD_RETRIES=3     # Retries per key command on failure
RUN_CMD_RETRY_WAIT=5  # Seconds between key command retries
SCENARIO_DURATION=30  # 40 minutes (change to 120 for quick test)
POWER_OFF_WAIT=30     # Seconds after power off before next on

CSV_FILE="Experiment_times.csv"
LOG_FILE="experiment_debug.log"

# PCAP server
PCAP_USER="het"
PCAP_HOST="129.10.227.207"
PCAP_BASE="/traffic/by-mac"
TV_MAC="14:c6:7d:15:31:56"
TV_NAME="Vizio"
PCAP_LOCAL="./data"

# TV connection (must match test.py)
# TV_IP = "10.19.37.243"
TV_IP = "192.168.14.120"
TV_PORT=7345

# Repetition counter (FAST → FAST2 → FAST3...)
declare -A REP_COUNT

# ==========================================
# Helper Functions
# ==========================================

tv_is_reachable() {
  # Quick TCP probe — returns 0 if TV API port is open
  python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
try:
    r = s.connect_ex(('$TV_IP', $TV_PORT))
    sys.exit(0 if r == 0 else 1)
finally:
    s.close()
" 2>/dev/null
}

wait_for_tv() {
  local attempt=1
  log "  Waiting for TV to become reachable..."
  sleep $BOOT_DELAY
  while ! tv_is_reachable; do
    if [[ $attempt -ge $MAX_BOOT_RETRIES ]]; then
      log "  ❌ TV still unreachable after $MAX_BOOT_RETRIES retries — re-sending WoL and giving up"
      python3 "$SCRIPT" on 2>/dev/null
      sleep $BOOT_DELAY
      if ! tv_is_reachable; then
        log "  ❌ FATAL: TV not reachable. Skipping remaining key presses."
        return 1
      fi
      return 0
    fi
    log "  TV not reachable (attempt $attempt/$MAX_BOOT_RETRIES) — re-sending WoL..."
    python3 "$SCRIPT" on 2>/dev/null
    sleep $BOOT_POLL_INTERVAL
    ((attempt++))
  done
  log "  ✅ TV is reachable."
  return 0
}

run_cmd() {
  local attempt=1
  while [[ $attempt -le $RUN_CMD_RETRIES ]]; do
    echo "  -> python3 $SCRIPT $*"
    local output
    output=$(python3 "$SCRIPT" "$@" 2>&1)
    echo "$output"
    # Check for network errors in the output
    if echo "$output" | grep -qiE "timed out|No route to host|Connection refused|Network is unreachable"; then
      log "  ⚠️  Command failed (attempt $attempt/$RUN_CMD_RETRIES): $*"
      if [[ $attempt -lt $RUN_CMD_RETRIES ]]; then
        # Check if TV is still reachable; if not, try to bring it back
        if ! tv_is_reachable; then
          log "  TV unreachable — attempting recovery..."
          wait_for_tv || return 1
        else
          sleep $RUN_CMD_RETRY_WAIT
        fi
      fi
      ((attempt++))
    else
      # Success (or non-network error)
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
  local label="$1" # e.g. "FAST"
  local step="$2"  # e.g. "[2/8]"

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

  powercycle
}

# ==========================================
# Ctrl+C safety
# ==========================================
trap 'echo ""; log "⚠️ Interrupted — powering off..."; python3 "$SCRIPT" off 2>/dev/null; exit 1' SIGINT SIGTERM

# ==========================================
# Run all scenarios once
# ==========================================

run_all() {
  # --- IDLE ---
  echo "[1/8] IDLE (Home Screen)..."
  run_scenario "IDLE" "[1/8]"

  # --- FAST ---
  echo "[2/8] FAST..."
  run_cmd input-cycle
  run_cmd key down
  run_cmd key ok
  sleep 20
  run_cmd key left
  run_cmd key left
  run_cmd key up
  run_cmd key up
  run_cmd key ok
  sleep 20
  run_cmd key down
  run_cmd key ok
  run_cmd key ok
  run_scenario "FAST" "[2/8]"

  # --- HDMI ---
  echo "[3/8] HDMI..."
  run_cmd input-cycle
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_scenario "HDMI" "[3/8]"

  # --- 14.1 Channel ---
  echo "[4/8] 14.1 Channel..."
  run_cmd key smartcast
  run_cmd key down
  run_cmd key ok
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  run_scenario "Antenna_14.1" "[4/8]"

  # --- Antenna Channel ---
  echo "[5/8] Antenna Channel..."
  run_cmd key smartcast
  run_cmd key down
  run_cmd key ok
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key down
  run_cmd key right
  run_cmd key ok
  run_scenario "Antenna" "[5/8]"

  # --- Netflix ---
  echo "[6/8] Netflix..."
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  sleep 40
  run_cmd key left
  sleep 360
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_cmd key left
  run_scenario "Netflix" "[6/8]"

  # --- YouTube ---
  echo "[7/8] YouTube..."
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key ok
  sleep 20
  run_cmd key left
  run_cmd key up
  run_cmd key right
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_scenario "Youtube" "[7/8]"

  # --- Tubi ---
  echo "[8/8] Tubi..."
  run_cmd key down
  run_cmd key down
  run_cmd key right
  run_cmd key right
  run_cmd key ok
  sleep 20
  run_cmd key ok
  run_cmd key ok
  run_scenario "Tubi" "[8/8]"
}

toggle_acr_off(){
  run_cmd key down
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_cmd key up
  run_cmd key ok
  run_cmd key up
  run_cmd key up
  run_cmd key ok
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key left
}

toggle_acr_on(){
  run_cmd key down
  run_cmd key left
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key ok
  run_cmd key up
  run_cmd key ok
  run_cmd key up
  run_cmd key up
  run_cmd key ok
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key down
  run_cmd key left
  run_cmd key right
  run_cmd key ok
  sleep 5
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

    # Create per-scenario directories
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
  log "Starting: ${REPS} rep(s), $((SCENARIO_DURATION / 60)) min each scenario"

  run_cmd on
  wait_for_tv

  for i in $(seq 1 "$REPS"); do
    log "══════ REPETITION $i / $REPS ══════"
    run_all
    log "══════  ══════"
    toggle_acr
    log "══════ ACR Toggled ══════"
    powercycle
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
  echo "Usage: $0 {run [N] | fetch | status}"
  echo "  run        Run all 8 scenarios once"
  echo "  run 3      Run all scenarios 3 times"
  echo "  fetch      Fetch PCAPs from server"
  echo "  status     Show experiment counts"
  ;;
esac
