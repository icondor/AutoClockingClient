@echo off
setlocal enabledelayedexpansion

:: Set up environment
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
set "LOG_DIR=%APP_SUPPORT%\Logs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

:: Create directories
echo Creating directories...
mkdir "%APP_SUPPORT%" 2>nul
mkdir "%LOG_DIR%" 2>nul

:: Create log file
set "LOG_FILE=%LOG_DIR%\install.log"
echo Installation started at %date% %time% > "%LOG_FILE%"

:: Kill any existing processes
echo Stopping existing processes...
taskkill /F /IM "power_monitor.exe" 2>>"%LOG_FILE%"
taskkill /F /IM "AttendanceTracker.exe" 2>>"%LOG_FILE%"
timeout /t 2 /nobreak >nul

:: Copy files
echo Copying files...
xcopy /Y "AttendanceTracker.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y "power_monitor.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y "config.json" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1

:: Create startup shortcut
echo Creating startup entry...
echo @echo off > "%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
echo start "" "%APP_SUPPORT%\power_monitor.exe" >> "%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
echo Created startup entry >> "%LOG_FILE%"

:: Start the monitor
echo Starting PowerMonitor...
start "" "%APP_SUPPORT%\power_monitor.exe" >>"%LOG_FILE%" 2>&1

:: Verify installation
timeout /t 2 /nobreak >nul
tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
    echo PowerMonitor started successfully >> "%LOG_FILE%"
) else (
    echo × Failed to start PowerMonitor
    echo Failed to start PowerMonitor >> "%LOG_FILE%"
    echo Attempting to start with shell execute... >> "%LOG_FILE%"
    powershell -Command "Start-Process -FilePath '%APP_SUPPORT%\power_monitor.exe'" >>"%LOG_FILE%" 2>&1
    timeout /t 2 /nobreak >nul
    tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
    if !errorlevel! equ 0 (
        echo ✓ PowerMonitor started successfully with alternative method
        echo PowerMonitor started successfully with alternative method >> "%LOG_FILE%"
    ) else (
        echo × Failed to start PowerMonitor with alternative method
        echo Failed to start PowerMonitor with alternative method >> "%LOG_FILE%"
        type "%LOG_FILE%"
        exit /b 1
    )
)

:: Check prerequisites
ver | find "10." >nul || (
    echo "Windows 10 or later required"
    echo "Windows 10 or later required" >> "%LOG_FILE%"
    exit /b 1
)

:: Verify disk space
dir /a /-c "%APPDATA%\" | find "bytes free" | for /f "tokens=1,2" %%a in ('more') do (
    if %%a LSS 10485760 (
        echo "Insufficient disk space"
        echo "Insufficient disk space" >> "%LOG_FILE%"
        exit /b 1
    )
)

echo Installation completed successfully
echo Installation completed successfully at %date% %time% >> "%LOG_FILE%"
exit /b 0 