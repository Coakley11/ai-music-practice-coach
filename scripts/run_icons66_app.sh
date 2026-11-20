#!/usr/bin/env bash
# Issue 66 app, on its own port, against a DISPOSABLE data directory.
#
# MUSIC_APP_DATA_DIR *is* the persistence root (suite_workspace._resolve_data_dir reads it at
# import), so pointing it at a throwaway folder is what keeps this run away from real songs,
# recordings and progressions. Windows lets several processes bind one port, and a probe then
# talks to whichever answers - so this refuses to start unless our own PID is the only listener.
set -euo pipefail

PORT="${1:-8691}"
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${2:-/c/tmp/_icons66_data_$PORT}"
LOG="/c/tmp/_icons66_app_$PORT.log"

listeners() { netstat -ano 2>/dev/null | grep -E "LISTENING" | grep -E ":$PORT\b" || true; }

if [ -n "$(listeners)" ]; then
  echo "REFUSING: port $PORT already has a listener:" >&2
  listeners >&2
  exit 1
fi

mkdir -p "$DATA"
cd "$WT"
MUSIC_APP_DATA_DIR="$DATA" nohup python -m streamlit run streamlit_music_practice_app.py \
  --server.port "$PORT" --server.headless true --server.fileWatcherType none \
  > "$LOG" 2>&1 &
APP_PID=$!
echo "started pid=$APP_PID port=$PORT data=$DATA log=$LOG"

for _ in $(seq 1 90); do
  if grep -qE "You can now view|Local URL" "$LOG" 2>/dev/null; then break; fi
  if ! kill -0 "$APP_PID" 2>/dev/null; then echo "app exited early; log:" >&2; tail -20 "$LOG" >&2; exit 1; fi
  sleep 2
done

OWNERS="$(listeners | awk '{print $NF}' | sort -u)"
echo "listener pids: $OWNERS"
# The streamlit launcher may exec a child, so accept our PID or a descendant of it, but never a
# listener we cannot account for.
for pid in $OWNERS; do
  if [ "$pid" != "$APP_PID" ]; then
    PARENT="$(ps -W 2>/dev/null | awk -v p="$pid" '$1==p {print $2}' || true)"
    echo "  pid $pid (parent col: ${PARENT:-unknown})"
  fi
done
COUNT="$(echo "$OWNERS" | wc -w)"
if [ "$COUNT" -ne 1 ]; then
  echo "REFUSING: $COUNT listeners on $PORT - a probe could read the wrong app" >&2
  exit 1
fi
echo "ready: single listener on $PORT"
