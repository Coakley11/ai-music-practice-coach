#!/usr/bin/env bash
# Karaoke QA acceptance run (Groups A, B, C).
#
# Carried over from the Issue 79 runner, and worth repeating: MUSIC_APP_DATA_DIR is read only
# by debug-dump code. The app writes its state into THIS WORKTREE's gitignored data/, so each
# run clears the ignored files there (git clean -fdX, which cannot touch tracked fixtures and
# cannot reach another worktree) and refuses to run in the main checkout, where that would
# clear the user's own app state.
set -u

PORT="${PORT:-8599}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${HERE}/scripts/evidence-karaoke-qa/server.log"
ARGS="${*:-}"
mkdir -p "$(dirname "$LOG")"

case "${HERE}" in
  */Documents/GitHub/ai-music-practice-coach)
    echo "REFUSING to run in the main checkout - this clears app state. Use a worktree."
    exit 2
    ;;
esac

if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:${PORT}/"; then
  echo "REFUSING to start: something is already serving port ${PORT}."
  exit 2
fi

echo "worktree : ${HERE}"
echo "port     : ${PORT}"

cd "${HERE}" || exit 1
git clean -fdXq data/ 2>/dev/null
echo "cleared  : ignored app state under ${HERE}/data (tracked fixtures kept)"

DATA="$(mktemp -d -t kqa-dumps-XXXXXX)"
# MUSIC_KARAOKE_RETUNE_TRACE is the app's own account of what a re-key attempt saw, and
# it exists because a browser run could not change the Practice Key during a performance
# and nothing on the page said why. Without it the acceptance can only report that the
# key did not move, which is a symptom and not a cause.
MUSIC_KARAOKE_RETUNE_TRACE=1 MUSIC_MT_KEY_TRACE=1 MUSIC_APP_DATA_DIR="${DATA}" \
  python -m streamlit run streamlit_music_practice_app.py \
  --server.port "${PORT}" --server.headless true --server.fileWatcherType none \
  > "${LOG}" 2>&1 &
SERVER=$!
echo "server pid: ${SERVER}"

for _ in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  if ! kill -0 "${SERVER}" 2>/dev/null; then
    echo "SERVER DIED before answering - last log lines:"
    tail -5 "${LOG}"
    exit 3
  fi
  sleep 2
done

# A curl cannot tell this script's server from someone else's on the same port. Confirm the
# process this script started is the one alive, or the whole run measures another app.
if ! kill -0 "${SERVER}" 2>/dev/null; then
  echo "REFUSING to continue: the server this script started is gone, so whatever answers on"
  echo "${PORT} belongs to something else. Last log lines:"
  tail -5 "${LOG}"
  exit 3
fi

# The acceptance reads the app's own traces (the synthesizer log, the retune log), which
# live under this directory, so it has to see the same one the server was given.
MUSIC_APP_DATA_DIR="${DATA}" python -X utf8 scripts/_accept_karaoke_qa.py "http://127.0.0.1:${PORT}" ${ARGS}
RC=$?

echo "stopping the server (pid ${SERVER})"
kill "${SERVER}" 2>/dev/null
sleep 2
kill -9 "${SERVER}" 2>/dev/null
rm -rf "${DATA}"
exit "${RC}"
