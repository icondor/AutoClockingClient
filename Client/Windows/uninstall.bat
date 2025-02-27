@echo off
setlocal enabledelayedexpansion

:: Kill processes
taskkill /F /IM "power_monitor.exe" 2>nul
taskkill /F /IM "AttendanceTracker.exe" 2>nul

:: Remove scheduled task
schtasks /Delete /TN "AttendanceTracker\PowerMonitor" /F 2>nul

:: Remove files
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
if exist "%APP_SUPPORT%" (
    rd /s /q "%APP_SUPPORT%"
)

echo Uninstallation completed successfully
exit /b 0 