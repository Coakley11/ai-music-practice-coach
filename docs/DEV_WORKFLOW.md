# Development workflow (`dev` branch)

## Branches

| Branch | Purpose |
|--------|---------|
| `dev` | Daily development, Cursor work, Streamlit Cloud **dev** app |
| `main` | Stable production — merge from `dev` only when ready |

## One-time setup (per clone)

```powershell
.\scripts\setup-dev-git.ps1
```

This checks out `dev`, sets upstream to `origin/dev`, and enables repo hooks in `.githooks/`.

## Push to dev (default)

```powershell
.\scripts\push-dev.ps1
```

Or:

```bash
git push origin dev
```

With `push.default=current` and upstream `origin/dev`, a plain `git push` on `dev` also goes to `origin/dev`.

## Protections

- **pre-push hook** blocks pushes to `main` unless `ALLOW_MAIN_PUSH=1`.
- Optional **post-commit auto-push**: set `AUTO_PUSH_DEV=1` to push `dev` after every commit.

## Streamlit Cloud

Point the dev app at branch **`dev`** in the dashboard (Settings → General → Branch). Pushes to `origin/dev` trigger redeploys.

## Merge to production (manual, later)

```bash
git checkout main
git merge dev
git push origin main   # requires ALLOW_MAIN_PUSH=1 if hook is enabled
```
