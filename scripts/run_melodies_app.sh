#!/usr/bin/env bash
# Issue 77A acceptance run.
#
# Two things this script refuses to let happen again, both of which produced measurements that
# looked real and were not:
#
#   1. STATE FROM A PREVIOUS RUN. MUSIC_APP_DATA_DIR *is* the app's persistence root
#      (suite_workspace._resolve_data_dir reads it at import), so each run gets its own fresh
#      directory - and the worktree's own gitignored data/ is cleared too, because some paths are
#      resolved relative to the checkout. A run that starts with the last run's layers already in
#      place proves nothing. It happened.
#
#   2. SOMEONE ELSE'S SERVER ON THE SAME PORT. Windows lets several processes bind one port, so
#      `curl` answering is no proof that the app under test is the one answering. Three of my own
#      servers were bound to one port during this investigation, and the probe was reading whichever
#      replied. This script therefore checks the port is free first, then confirms that the ONLY
#      listener afterwards is the process it started.
set -u

PORT="${PORT:-8641}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
EVID="${HERE}/scripts/evidence-melodies-after"
LOG="${EVID}/server.log"
mkdir -p "${EVID}"

case "${HERE}" in
  */Documents/GitHub/ai-music-practice-coach)
    echo "REFUSING to run in the main checkout - this clears app state. Use a worktree."
    exit 2
    ;;
esac

listeners() {
  netstat -ano 2>/dev/null | grep -E ":${PORT}[[:space:]].*LISTENING" | awk '{print $NF}' | sort -u
}

if [ -n "$(listeners)" ]; then
  echo "REFUSING to start: something is already listening on ${PORT} (pid(s): $(listeners | tr '\n' ' '))."
  echo "Pick a free port, or stop that server if it is yours. Driving someone else's app"
  echo "produces results that look real and are not."
  exit 2
fi

cd "${HERE}" || exit 1
git clean -fdXq data/ 2>/dev/null
echo "worktree : ${HERE}"
echo "port     : ${PORT}"
echo "cleared  : ignored app state under ${HERE}/data (tracked fixtures kept)"

DATA="$(mktemp -d -t pdf-root-XXXXXX)"
echo "data root: ${DATA}"
MUSIC_APP_DATA_DIR="${DATA}" python -m streamlit run streamlit_music_practice_app.py \
  --server.port "${PORT}" --server.headless true --server.fileWatcherType none \
  > "${LOG}" 2>&1 &
SERVER=$!
echo "server pid (shell): ${SERVER}"

for _ in $(seq 1 90); do
  if curl -s -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  if ! kill -0 "${SERVER}" 2>/dev/null; then
    echo "SERVER DIED before answering - last log lines:"
    tail -8 "${LOG}"
    exit 3
  fi
  sleep 2
done

OWNERS="$(listeners | tr '\n' ' ')"
COUNT="$(listeners | wc -l | tr -d ' ')"
echo "listener pid(s): ${OWNERS}"
if [ "${COUNT}" -ne 1 ]; then
  echo "REFUSING to continue: ${COUNT} processes are listening on ${PORT}, so the results would not"
  echo "say which app they came from."
  kill "${SERVER}" 2>/dev/null
  exit 3
fi

python scripts/_accept_uploaded_melodies_pdf.py "http://127.0.0.1:${PORT}" --tag "${TAG:-after}"
RC=$?

echo "stopping the server"
kill "${SERVER}" 2>/dev/null
sleep 2
pkill -f "server.port ${PORT}" 2>/dev/null
rm -rf "${DATA}"
exit "${RC}"
