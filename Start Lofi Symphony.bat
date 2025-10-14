@echo off
setlocal
cd /d "%~dp0"
python "launcher.py" %*
if errorlevel 1 (
    echo.
    echo Launch failed. Review the messages above for details.
) else (
    echo.
    echo LofiSymphony closed. You can run this shortcut again any time.
)
pause
