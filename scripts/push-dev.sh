#!/usr/bin/env sh
# Push dev branch to origin/dev.
set -e
cd "$(dirname "$0")/.."

branch=$(git branch --show-current)
if [ "$branch" != "dev" ]; then
  echo "Switching to dev..."
  git checkout dev
fi

git branch --set-upstream-to=origin/dev dev 2>/dev/null || true
echo "Pushing dev -> origin/dev ..."
git push origin dev
echo "Done. Streamlit Cloud (dev app) should redeploy from origin/dev."
