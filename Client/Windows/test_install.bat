@echo off
setlocal enabledelayedexpansion

set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
set "LOG_DIR=%APP_SUPPORT%\Logs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "CURRENT_DIR=%~dp0"

echo Starting AttendanceTracker installation...

echo Creating directories...
mkdir "%APP_SUPPORT%" 2>nul
mkdir "%LOG_DIR%" 2>nul

set "LOG_FILE=%LOG_DIR%\install.log"
echo Installation started at %date% %time% > "%LOG_FILE%"
echo Current directory: %CURRENT_DIR% >> "%LOG_FILE%"
echo Target directory: %APP_SUPPORT% >> "%LOG_FILE%"

echo Stopping existing processes...
taskkill /F /IM "power_monitor.exe" 2>>"%LOG_FILE%" || echo No existing power_monitor process found >> "%LOG_FILE%"
taskkill /F /IM "AttendanceTracker.exe" 2>>"%LOG_FILE%" || echo No existing AttendanceTracker process found >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul

echo Copying files...
echo Copying from %CURRENT_DIR% to %APP_SUPPORT% >> "%LOG_FILE%"
xcopy /Y /F "%CURRENT_DIR%AttendanceTracker.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y /F "%CURRENT_DIR%power_monitor.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y /F "%CURRENT_DIR%config.json" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1

if not exist "%APP_SUPPORT%\power_monitor.exe" (
    echo Error: power_monitor.exe not found in target directory >> "%LOG_FILE%"
    echo Error: power_monitor.exe not found in target directory
    exit /b 1
)

echo Creating startup entry...
(
    echo @echo off
    echo cd /d "%APP_SUPPORT%"
    echo start "" /B "%APP_SUPPORT%\power_monitor.exe"
) > "%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
echo Created startup entry >> "%LOG_FILE%"

echo Starting PowerMonitor...
cd /d "%APP_SUPPORT%"
echo Current directory before start: %CD% >> "%LOG_FILE%"
echo Attempting to start power_monitor.exe silently... >> "%LOG_FILE%"
start "" /B "%APP_SUPPORT%\power_monitor.exe" 2>>"%LOG_DIR%\error1.log"
timeout /t 3 /nobreak >nul
tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
    echo PowerMonitor started successfully >> "%LOG_FILE%"
) else (
    echo × Failed to start PowerMonitor, checking error logs...
    if exist "%LOG_DIR%\error1.log" (
        type "%LOG_DIR%\error1.log" >> "%LOG_FILE%"
        type "%LOG_DIR%\error1.log"
    )
    echo --- Directory Contents ---
    dir "%APP_SUPPORT%" >> "%LOG_FILE%"
    dir "%APP_SUPPORT%"
    exit /b 1
)

echo Installation completed successfully
echo Installation completed successfully at %date% %time% >> "%LOG_FILE%"
exit /b 0