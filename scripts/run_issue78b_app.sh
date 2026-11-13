#!/usr/bin/env bash
# Issue 78B acceptance run.
#
# IMPORTANT, and not what an earlier version of this script assumed: MUSIC_APP_DATA_DIR is read
# only by debug-dump code (backing_context, backing_key_cycle). It is NOT the app's persistence
# root. The app writes its state into THIS WORKTREE's gitignored data/ directory, so:
#
#   * the user's real data is untouched only because a worktree has its own data/ - verify the main
#     checkout's data/ separately rather than trusting an environment variable, and
#   * state leaks from one run to the next unless it is cleared first. It did: a run started with
#     the previous run's three takes already in place, which made its results meaningless.
#
# So each run clears the IGNORED files under this worktree's data/ (git clean -fdX, which cannot
# touch tracked fixtures and cannot reach any other worktree) and never runs in the main checkout.
set -u

PORT="${PORT:-8595}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${HERE}/scripts/evidence-issue78b/server.log"
mkdir -p "$(dirname "$LOG")"

case "${HERE}" in
  */Documents/GitHub/ai-music-practice-coach)
    echo "REFUSING to run in the main checkout - this clears app state. Use a worktree."
    exit 2
    ;;
esac

echo "worktree : ${HERE}"
echo "port     : ${PORT}"

cd "${HERE}" || exit 1
git clean -fdXq data/ 2>/dev/null
echo "cleared  : ignored app state under ${HERE}/data (tracked fixtures kept)"

DATA="$(mktemp -d -t i78b-dumps-XXXXXX)"   # only for the debug dumps that DO read this variable
MUSIC_APP_DATA_DIR="${DATA}" python -m streamlit run streamlit_music_practice_app.py \
  --server.port "${PORT}" --server.headless true --server.fileWatcherType none \
  > "${LOG}" 2>&1 &
SERVER=$!
echo "server pid: ${SERVER}"

for _ in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  sleep 2
done

python scripts/_accept_issue78b_app.py "http://127.0.0.1:${PORT}"
RC=$?

echo "stopping the server (pid ${SERVER})"
kill "${SERVER}" 2>/dev/null
sleep 2
kill -9 "${SERVER}" 2>/dev/null
rm -rf "${DATA}"
exit "${RC}"
