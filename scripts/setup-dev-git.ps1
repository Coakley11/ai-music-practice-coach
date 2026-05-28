# One-time (per clone) setup: dev as default development branch, hooks, upstream.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Configuring local git for dev-first workflow..."

$current = git branch --show-current
if ($current -ne "dev") {
    git checkout dev
    if ($LASTEXITCODE -ne 0) {
        git checkout -b dev origin/dev
    }
}

git config --local branch.dev.remote origin
git config --local branch.dev.merge refs/heads/dev
git config --local branch.dev.pushRemote origin
git config --local push.default current
git config --local push.autoSetupRemote true
git config --local core.hooksPath .githooks

git branch --set-upstream-to=origin/dev dev

Write-Host ""
Write-Host "Configured:"
git config --local --get-regexp "^(branch\.dev\.|push\.|core\.hooksPath)"
Write-Host ""
Write-Host "Current branch:" (git branch --show-current)
Write-Host "Upstream:" (git rev-parse --abbrev-ref "@{u}")
Write-Host ""
Write-Host "Push to dev:  .\scripts\push-dev.ps1"
Write-Host "Optional auto-push after commit: `$env:AUTO_PUSH_DEV='1'"
Write-Host "main is protected by .githooks/pre-push (use ALLOW_MAIN_PUSH=1 to override)."
