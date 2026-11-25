#!/usr/bin/env bash
# All three widths, one after another, each against its own app and its own DISPOSABLE data dir.
#
# A shared MUSIC_APP_DATA_DIR leaked the previous run's chosen key and accumulated its chords into
# the next run, which produced a false failure at 390 px and a ground truth computed from
# already-transposed chords. One data directory per width is what makes each run independent.
set -uo pipefail

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WT"
LOG="${1:-/c/tmp/_icons66w_all.log}"
: > "$LOG"

stop_port() {
  local port="$1"
  local pids
  pids="$(netstat -ano 2>/dev/null | grep -E 'LISTENING' | grep -E ":$port\b" | awk '{print $NF}' | sort -u)"
  for pid in $pids; do
    powershell -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1
  done
  sleep 2
}

run_width() {
  local port="$1" width="$2"
  local data="/c/tmp/_icons66w_data_${width}_$port"
  echo "" >> "$LOG"
  echo "================ $width px (port $port, data $data) ================" >> "$LOG"
  stop_port "$port"
  rm -rf "$data"
  if ! bash scripts/run_icons66_app.sh "$port" "$data" >> "$LOG" 2>&1; then
    echo "APP FAILED TO START at $width px" >> "$LOG"
    return 1
  fi
  timeout 2400 python -I scripts/_accept_issue66_editor_icons.py "http://127.0.0.1:$port" --width "$width" \
    >> "$LOG" 2>&1
  local rc=$?
  echo "exit code at $width px: $rc" >> "$LOG"
  stop_port "$port"
  rm -rf "$data"
  return $rc
}

run_width 8691 1500
run_width 8692 390
run_width 8693 360

echo "" >> "$LOG"
echo "=== SUMMARY ===" >> "$LOG"
grep -E "gates passed at|OBSERVATION|exit code at" "$LOG" >> "$LOG"
echo "ACCEPTANCE RUNS COMPLETE" >> "$LOG"
