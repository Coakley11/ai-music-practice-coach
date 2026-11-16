#!/usr/bin/env bash
# Start the app and run one karaoke acceptance script against it.
#
#   bash scripts/run_karaoke_script.sh scripts/_accept_karaoke_scroll_live.py 8606
#
# The repeated lessons, kept in one place: the app writes its state into THIS WORKTREE's
# gitignored data/ (so each run clears it and the script refuses to run in the main checkout);
# the acceptance reads the app's own traces, so it is given the same MUSIC_APP_DATA_DIR the
# server gets; and the script this runs is never edited while it runs - bash re-reads a running
# script from a byte offset and resumes mid-line if the file has changed under it.
set -u

SCRIPT="${1:?usage: run_karaoke_script.sh <acceptance script> [port]}"
PORT="${2:-8606}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TAG="$(basename "${SCRIPT}" .py)"
LOG="${HERE}/scripts/evidence-karaoke-qa/server-${TAG}.log"
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
echo "script   : ${SCRIPT}"
echo "port     : ${PORT}"

cd "${HERE}" || exit 1
git clean -fdXq data/ 2>/dev/null
echo "cleared  : ignored app state under ${HERE}/data (tracked fixtures kept)"

DATA="$(mktemp -d -t kqa-run-XXXXXX)"
MUSIC_KARAOKE_RETUNE_TRACE=1 MUSIC_APP_DATA_DIR="${DATA}" \
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

if ! kill -0 "${SERVER}" 2>/dev/null; then
  echo "REFUSING to continue: the server this script started is gone, so whatever answers on"
  echo "${PORT} belongs to something else."
  tail -5 "${LOG}"
  exit 3
fi

MUSIC_APP_DATA_DIR="${DATA}" python -X utf8 -u "${SCRIPT}" "http://127.0.0.1:${PORT}" ${EXTRA:-}
RC=$?

echo "stopping the server (pid ${SERVER})"
kill "${SERVER}" 2>/dev/null
sleep 2
kill -9 "${SERVER}" 2>/dev/null
rm -rf "${DATA}"
exit "${RC}"
