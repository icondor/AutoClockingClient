@echo off
echo Starting AttendanceTracker installation...

:: Get the directory where this script is located
cd /d "%~dp0"

:: Run the installation script
call test_install.bat

:: Show installation status
echo.
echo Current running processes:
tasklist | findstr "power_monitor.exe"
tasklist | findstr "AttendanceTracker.exe"

:: Keep window open for feedback
echo.
echo Press any key to close this window...
pause >nul 