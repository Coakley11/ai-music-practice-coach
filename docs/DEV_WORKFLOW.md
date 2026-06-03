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

Point the **dev** app at branch **`dev`** in the dashboard (**Settings → General → Branch**). Pushes to `origin/dev` usually trigger an automatic redeploy (allow 1–3 minutes).

### Verify the dev app is actually on `dev`

1. **GitHub:** `origin/dev` tip should match the commit you expect (e.g. `git log -1 origin/dev`).
2. **Streamlit Cloud:** open the **dev** app → **Manage app** → confirm **Branch = `dev`** (not `main`). Production often tracks `main` at `c86e1e6…`; navigation UI changes are only on `dev`.
3. **In the running app:** look for the green bottom banner  
   `Navigation UI version c28e946+deploy-marker-1 loaded`  
   and sidebar caption `Nav UI · c28e946+deploy-marker-1`.  
   - **Marker missing** → deployment/branch/cached app issue (wrong branch, redeploy not finished, or wrong URL). Try **Reboot app** in Streamlit Cloud, then hard refresh the browser (`Ctrl+Shift+R` / `Cmd+Shift+R`).
   - **Marker visible but arrows wrong** → CSS/JS pinning issue in the browser (not deployment).
4. **Manual redeploy:** Streamlit Cloud → **Manage app** → **Reboot app** (or delete + redeploy) if pushes do not appear after several minutes.
5. **Browser:** hard refresh after redeploy; optional private window to avoid cached HTML.

## Merge to production (manual, later)

```bash
git checkout main
git merge dev
git push origin main   # requires ALLOW_MAIN_PUSH=1 if hook is enabled
```
