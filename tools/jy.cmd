@echo off
setlocal enabledelayedexpansion
rem Portable JianYing CLI wrapper. No hard-coded paths.
rem Env is discovered by tools\jy_env.py into tools\jy.env (delete it to re-detect).
set "HERE=%~dp0"
set "PY=python"
if defined JY_PYTHON set "PY=%JY_PYTHON%"

if not exist "%HERE%jy.env" (
  "%PY%" "%HERE%jy_env.py" --write-env >nul 2>&1
)

for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%HERE%jy.env") do (
  if not "%%a"=="" set "%%a=%%b"
)

if not defined APP_VERSION (
  echo [jy] environment not detected, re-running jy_env.py ...
  "%PY%" "%HERE%jy_env.py" --write-env
)

if defined APP_VERSION set "JY_APP_VERSION=%APP_VERSION%"
if defined NEW_VERSION set "JY_DRAFT_NEW_VERSION=%NEW_VERSION%"
if not defined SKILL_SCRIPTS goto :noskill

pushd "%SKILL_SCRIPTS%"
"%PY%" -X utf8 -m jyai.cli %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:noskill
echo [jy] skill scripts not found.
echo      run: python tools\jy_env.py --write-env
exit /b 2