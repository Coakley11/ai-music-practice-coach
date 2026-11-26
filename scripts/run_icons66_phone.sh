#!/usr/bin/env bash
set -uo pipefail
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WT"
LOG="${1:-/c/tmp/_icons66w_phone.log}"
: > "$LOG"
stop_port() {
  local port="$1" pids
  pids="$(netstat -ano 2>/dev/null | grep -E 'LISTENING' | grep -E ":$port\b" | awk '{print $NF}' | sort -u)"
  for pid in $pids; do powershell -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1; done
  sleep 2
}
run_width() {
  local port="$1" width="$2"
  local data="/c/tmp/_icons66p_data_${width}_$port"
  echo "" >> "$LOG"; echo "================ $width px ================" >> "$LOG"
  stop_port "$port"; rm -rf "$data"
  bash scripts/run_icons66_app.sh "$port" "$data" >> "$LOG" 2>&1 || { echo "APP FAILED at $width" >> "$LOG"; return 1; }
  timeout 2400 python -I scripts/_accept_issue66_editor_icons.py "http://127.0.0.1:$port" --width "$width" >> "$LOG" 2>&1
  echo "exit code at $width px: $?" >> "$LOG"
  stop_port "$port"; rm -rf "$data"
}
run_width 8695 390
run_width 8696 360
echo "PHONE RUNS COMPLETE" >> "$LOG"
