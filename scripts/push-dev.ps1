# Push current dev branch to origin/dev (default development remote).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$branch = git branch --show-current
if ($branch -ne "dev") {
    Write-Host "Switching to dev branch..."
    git checkout dev
}

$upstream = git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null
if (-not $upstream -or $upstream -ne "origin/dev") {
    git branch --set-upstream-to=origin/dev dev
}

Write-Host "Pushing dev -> origin/dev ..."
git push origin dev
if ($LASTEXITCODE -eq 0) {
    Write-Host "Done. Streamlit Cloud (dev app) should redeploy from origin/dev."
}
