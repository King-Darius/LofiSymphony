@echo off
setlocal
cd /d "%~dp0"

set "LAUNCH_CMD="
where py >nul 2>&1
if %errorlevel%==0 set "LAUNCH_CMD=py -3"

if not defined LAUNCH_CMD (
    where python >nul 2>&1
    if %errorlevel%==0 set "LAUNCH_CMD=python"
)

if not defined LAUNCH_CMD (
    echo.
    echo Python 3.9 or newer is required to run LofiSymphony.
    echo Download it from https://www.python.org/downloads/ and then run this shortcut again.
    goto :missing_python
)

%LAUNCH_CMD% -c "import sys; raise SystemExit(0 if (3, 9) <= sys.version_info < (3, 13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo This launcher needs Python between 3.9 and 3.12.
    echo Install a supported version from https://www.python.org/downloads/ and then run this shortcut again.
    goto :missing_python
)

%LAUNCH_CMD% "launcher.py" %*
if errorlevel 1 (
    echo.
    echo Launch failed. Review the messages above for details.
) else (
    echo.
    echo LofiSymphony closed. You can run this shortcut again any time.
)
pause
goto :eof

:missing_python
pause
