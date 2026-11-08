@echo off
setlocal
rem Branch-safe dual-repo sync: fetch -> guard branch -> stage/commit ->
rem non-fast-forward check -> push HEAD:main. Failures are reported and
rem never auto-retried. Usage: push_all.bat "message" [--allow-non-main]

set "MSG=%~1"
if "%MSG%"=="" set "MSG=chore: sync intelligence platform and pipeline updates"
set "ALLOW=%~2"
set "FAILED=0"

echo =================================================
echo   Dual-Repo Multi-Push (Public + Private)
echo =================================================

echo.
echo [1/2] Syncing Public Repo: gujrera-intelligence...
git fetch origin
if errorlevel 1 (
    echo   FETCH FAILED - aborting public repo.
    set "FAILED=1"
    goto sync_private
)
for /f %%i in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%i"
if not "%BRANCH%"=="main" if not "%ALLOW%"=="--allow-non-main" (
    echo   ABORTED: current branch is '%BRANCH%', not 'main'.
    echo   Either commit on main, re-run with --allow-non-main, or push explicitly:
    echo     git push origin %BRANCH%:main
    set "FAILED=1"
    goto sync_private
)
git add .
git diff-index --quiet HEAD || git commit -m "%MSG%"
if errorlevel 1 (
    echo   COMMIT FAILED - aborting public repo.
    set "FAILED=1"
    goto sync_private
)
for /f "tokens=1,2" %%a in ('git rev-list --left-right --count HEAD...origin/main') do set "AHEAD=%%a" & set "BEHIND=%%b"
if not "%BEHIND%"=="0" (
    echo   ABORTED: origin/main is %BEHIND% commit(s) ahead of local '%BRANCH%'. Reconcile first:
    echo     git pull --rebase origin main
    set "FAILED=1"
    goto sync_private
)
git push origin HEAD:main
if errorlevel 1 (
    echo   PUSH FAILED - aborting public repo.
    set "FAILED=1"
    goto sync_private
)
echo   -> Public repository pushed.

:sync_private
echo.
echo [2/2] Syncing Private Repo: gujrera-pipeline...
pushd gujrera_pipeline
git fetch origin
if errorlevel 1 (
    echo   FETCH FAILED - aborting private repo.
    set "FAILED=1"
    goto done
)
for /f %%i in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%i"
if not "%BRANCH%"=="main" if not "%ALLOW%"=="--allow-non-main" (
    echo   ABORTED: current branch is '%BRANCH%', not 'main'.
    echo   Either commit on main, re-run with --allow-non-main, or push explicitly:
    echo     git push origin %BRANCH%:main
    set "FAILED=1"
    goto done
)
git add .
git diff-index --quiet HEAD || git commit -m "%MSG%"
if errorlevel 1 (
    echo   COMMIT FAILED - aborting private repo.
    set "FAILED=1"
    goto done
)
for /f "tokens=1,2" %%a in ('git rev-list --left-right --count HEAD...origin/main') do set "AHEAD=%%a" & set "BEHIND=%%b"
if not "%BEHIND%"=="0" (
    echo   ABORTED: origin/main is %BEHIND% commit(s) ahead of local '%BRANCH%'. Reconcile first:
    echo     git pull --rebase origin main
    set "FAILED=1"
    goto done
)
git push origin HEAD:main
if errorlevel 1 (
    echo   PUSH FAILED - aborting private repo.
    set "FAILED=1"
    goto done
)
echo   -> Private repository pushed.

:done
popd

echo.
if "%FAILED%"=="1" (
    echo SYNC INCOMPLETE - see messages above. Nothing was retried automatically.
    endlocal & exit /b 1
)
echo All repositories synchronized successfully!
endlocal
