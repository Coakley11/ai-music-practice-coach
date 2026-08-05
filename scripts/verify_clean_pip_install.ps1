#!/usr/bin/env pwsh
# Verify requirements install without numba/llvmlite Python-version failures (Python 3.12).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$venv = Join-Path $repo ".venv-clean-install-test"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
py -3.12 -m venv $venv
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\pip.exe") install -r (Join-Path $repo "requirements.txt")
& (Join-Path $venv "Scripts\python.exe") -c "import librosa, numba, llvmlite; print('librosa', librosa.__version__, 'numba', numba.__version__, 'llvmlite', llvmlite.__version__)"
Write-Host "clean_install_ok"
