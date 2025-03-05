@echo off
setlocal enabledelayedexpansion

:: Kill running processes
taskkill /F /IM "PowerMonitor.exe" 2>nul
taskkill /F /IM "AttendanceTracker.exe" 2>nul

:: Remove scheduled task (if applicable)
schtasks /Delete /TN "AttendanceTracker\PowerMonitor" /F 2>nul

:: Remove the startup script
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "STARTUP_SCRIPT=%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
if exist "%STARTUP_SCRIPT%" (
    del "%STARTUP_SCRIPT%"
    echo Removed startup script
)

:: Remove the application directory
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
if exist "%APP_SUPPORT%" (
    rd /s /q "%APP_SUPPORT%"
)

echo Uninstallation completed successfully
exit /b 0