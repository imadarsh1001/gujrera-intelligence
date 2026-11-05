@echo off
set "MSG=%~1"
if "%MSG%"=="" set "MSG=chore: sync intelligence platform and pipeline updates"

echo =================================================
echo   Dual-Repo Multi-Push (Public + Private)
echo =================================================

echo.
echo [1/2] Syncing Public Repo: gujrera-intelligence...
git add .
git diff-index --quiet HEAD || git commit -m "%MSG%"
git push origin main

echo.
echo [2/2] Syncing Private Repo: gujrera-pipeline...
pushd gujrera_pipeline
git add .
git diff-index --quiet HEAD || git commit -m "%MSG%"
git push origin main
popd

echo.
echo All repositories synchronized successfully!
