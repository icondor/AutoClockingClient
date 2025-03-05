@echo off
setlocal enabledelayedexpansion

:: Set up environment with proper paths
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
set "LOG_DIR=%APP_SUPPORT%\Logs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "CURRENT_DIR=%~dp0"

echo Starting AttendanceTracker installation...

:: Create directories
echo Creating directories...
if not exist "%APP_SUPPORT%" (
    mkdir "%APP_SUPPORT%" 2>nul
    if errorlevel 1 (
        echo Failed to create app directory - permission denied
        exit /b 1
    )
)

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%" 2>nul
    if errorlevel 1 (
        echo Failed to create log directory - permission denied
        exit /b 1
    )
)

:: Create log file
set "LOG_FILE=%LOG_DIR%\install.log"
echo Installation started at %date% %time% > "%LOG_FILE%" || (
    echo Failed to create log file - permission denied
    exit /b 1
)
echo Current directory: %CURRENT_DIR% >> "%LOG_FILE%"
echo Target directory: %APP_SUPPORT% >> "%LOG_FILE%"

:: Kill any existing processes
echo Stopping existing processes...
taskkill /F /IM "PowerMonitor.exe" 2>>"%LOG_FILE%" || echo No existing PowerMonitor process found >> "%LOG_FILE%"
taskkill /F /IM "AttendanceTracker.exe" 2>>"%LOG_FILE%" || echo No existing AttendanceTracker process found >> "%LOG_FILE%"

:: Verify processes are stopped
timeout /t 2 /nobreak >nul
tasklist /FI "IMAGENAME eq PowerMonitor.exe" 2>nul | find "PowerMonitor.exe" >nul
if !errorlevel! equ 0 (
    echo Failed to stop PowerMonitor.exe
    echo Failed to stop PowerMonitor.exe >> "%LOG_FILE%"
    exit /b 1
)

:: Copy files
echo Copying files...
echo Copying from %CURRENT_DIR% to %APP_SUPPORT% >> "%LOG_FILE%"

if not exist "%CURRENT_DIR%AttendanceTracker.exe" (
    echo Error: AttendanceTracker.exe not found in source directory
    echo Error: AttendanceTracker.exe not found in source directory >> "%LOG_FILE%"
    exit /b 1
)
if not exist "%CURRENT_DIR%PowerMonitor.exe" (
    echo Error: PowerMonitor.exe not found in source directory
    echo Error: PowerMonitor.exe not found in source directory >> "%LOG_FILE%"
    exit /b 1
)
if not exist "%CURRENT_DIR%config.json" (
    echo Error: config.json not found in source directory
    echo Error: config.json not found in source directory >> "%LOG_FILE%"
    exit /b 1
)

xcopy /Y /F "%CURRENT_DIR%AttendanceTracker.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
if not exist "%APP_SUPPORT%\AttendanceTracker.exe" (
    echo Error: Failed to copy AttendanceTracker.exe
    echo Error: Failed to copy AttendanceTracker.exe >> "%LOG_FILE%"
    exit /b 1
)

xcopy /Y /F "%CURRENT_DIR%PowerMonitor.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
if not exist "%APP_SUPPORT%\PowerMonitor.exe" (
    echo Error: Failed to copy PowerMonitor.exe
    echo Error: Failed to copy PowerMonitor.exe >> "%LOG_FILE%"
    exit /b 1
)

xcopy /Y /F "%CURRENT_DIR%config.json" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
if not exist "%APP_SUPPORT%\config.json" (
    echo Error: Failed to copy config.json
    echo Error: Failed to copy config.json >> "%LOG_FILE%"
    exit /b 1
)

:: Create startup entry
echo Creating startup entry...
set "STARTUP_SCRIPT=%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
(
    echo @echo off
    echo cd /d "%APP_SUPPORT%"
    echo start "" /B "%APP_SUPPORT%\PowerMonitor.exe"
) > "%STARTUP_SCRIPT%" || (
    echo Failed to create startup entry
    echo Failed to create startup entry >> "%LOG_FILE%"
    exit /b 1
)

if not exist "%STARTUP_SCRIPT%" (
    echo Error: Startup script not created
    echo Error: Startup script not created >> "%LOG_FILE%"
    exit /b 1
)
echo Created startup entry >> "%LOG_FILE%"

:: Start PowerMonitor
echo Starting PowerMonitor...
cd /d "%APP_SUPPORT%" || (
    echo Failed to change directory
    echo Failed to change directory >> "%LOG_FILE%"
    exit /b 1
)
start "" /B "%APP_SUPPORT%\PowerMonitor.exe"

:: Verify process started
timeout /t 3 /nobreak >nul
tasklist /FI "IMAGENAME eq PowerMonitor.exe" | find "PowerMonitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
    echo PowerMonitor started successfully >> "%LOG_FILE%"
) else (
    echo × Failed to start PowerMonitor
    echo Failed to start PowerMonitor >> "%LOG_FILE%"
    exit /b 1
)

echo Installation completed successfully
echo Installation completed successfully at %date% %time% >> "%LOG_FILE%"
exit /b 0