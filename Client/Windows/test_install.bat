@echo off
setlocal enabledelayedexpansion

:: Set up environment
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
set "LOG_DIR=%APP_SUPPORT%\Logs"

:: Create directories
mkdir "%APP_SUPPORT%" 2>nul
mkdir "%LOG_DIR%" 2>nul

:: Kill any existing processes
taskkill /F /IM "power_monitor.exe" 2>nul
taskkill /F /IM "AttendanceTracker.exe" 2>nul

:: Copy files
echo Copying files...
xcopy /Y "AttendanceTracker.exe" "%APP_SUPPORT%\" >nul
xcopy /Y "power_monitor.exe" "%APP_SUPPORT%\" >nul
xcopy /Y "config.json" "%APP_SUPPORT%\" >nul

:: Create scheduled task for power_monitor
echo Creating scheduled task...
schtasks /Create /TN "AttendanceTracker\PowerMonitor" /TR "'%APP_SUPPORT%\power_monitor.exe'" /SC ONLOGON /IT /NP /RL LIMITED /F

:: Start the monitor
echo Starting PowerMonitor...
start "" "%APP_SUPPORT%\power_monitor.exe"

:: Verify installation
timeout /t 2 /nobreak >nul
tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
) else (
    echo × Failed to start PowerMonitor
    exit /b 1
)

echo Installation completed successfully
exit /b 0 