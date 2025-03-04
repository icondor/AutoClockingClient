@echo off
setlocal enabledelayedexpansion

:: Set up environment with proper paths
set "APP_SUPPORT=%APPDATA%\AttendanceTracker"
set "LOG_DIR=%APP_SUPPORT%\Logs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "CURRENT_DIR=%~dp0"

echo Starting AttendanceTracker installation...

:: Create directories (don't fail if they exist)
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
    echo Failed to stop power_monitor.exe
    echo Failed to stop power_monitor.exe >> "%LOG_FILE%"
    exit /b 1
)

:: Copy files with full paths and verification
echo Copying files...
echo Copying from %CURRENT_DIR% to %APP_SUPPORT% >> "%LOG_FILE%"

:: Check source files exist
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

:: Copy files
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

:: Create startup entry with error checking
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

:: Verify startup script was created
if not exist "%STARTUP_SCRIPT%" (
    echo Error: Startup script not created
    echo Error: Startup script not created >> "%LOG_FILE%"
    exit /b 1
)
echo Created startup entry >> "%LOG_FILE%"

:: Start the monitor with full path and error capture
echo Starting PowerMonitor...
cd /d "%APP_SUPPORT%" || (
    echo Failed to change directory
    echo Failed to change directory >> "%LOG_FILE%"
    exit /b 1
)
echo Current directory before start: %CD% >> "%LOG_FILE%"

:: Try method 1: Start silently in background
echo Method 1: Background start >> "%LOG_FILE%"
start "" /B "%APP_SUPPORT%\PowerMonitor.exe" > "%LOG_DIR%\output1.log" 2> "%LOG_DIR%\error1.log"

:: Verify process started
timeout /t 3 /nobreak >nul
tasklist /FI "IMAGENAME eq PowerMonitor.exe" | find "PowerMonitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
    echo PowerMonitor started successfully >> "%LOG_FILE%"
) else (
    echo × Failed with method 1, checking error logs...
    echo --- Method 1 Error Log ---
    if exist "%LOG_DIR%\error1.log" (
        type "%LOG_DIR%\error1.log"
        type "%LOG_DIR%\error1.log" >> "%LOG_FILE%"
    )
    if exist "%LOG_DIR%\output1.log" (
        type "%LOG_DIR%\output1.log"
        type "%LOG_DIR%\output1.log" >> "%LOG_FILE%"
    )
    
    @REM echo Trying method 2... >> "%LOG_FILE%"
    @REM :: Try method 2: PowerShell background start
    @REM echo Method 2: PowerShell background start >> "%LOG_FILE%"
    @REM powershell -Command "Start-Process '%APP_SUPPORT%\power_monitor.exe' -WindowStyle Hidden -RedirectStandardError '%LOG_DIR%\error2.log' -RedirectStandardOutput '%LOG_DIR%\output2.log'" >> "%LOG_FILE%" 2>&1
    
    @REM timeout /t 3 /nobreak >nul
    @REM tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
    @REM if !errorlevel! equ 0 (
    @REM     echo ✓ PowerMonitor started successfully with method 2
    @REM     echo PowerMonitor started successfully with method 2 >> "%LOG_FILE%"
    @REM ) else (
    @REM     echo × Failed with method 2, checking error logs...
    @REM     echo --- Method 2 Error Log ---
    @REM     if exist "%LOG_DIR%\error2.log" (
    @REM         type "%LOG_DIR%\error2.log"
    @REM         type "%LOG_DIR%\error2.log" >> "%LOG_FILE%"
    @REM     )
    @REM     if exist "%LOG_DIR%\output2.log" (
    @REM         type "%LOG_DIR%\output2.log"
    @REM         type "%LOG_DIR%\output2.log" >> "%LOG_FILE%"
    @REM     )
        
    @REM     echo Trying method 3... >> "%LOG_FILE%"
    @REM     :: Try method 3: Direct execution with error capture
    @REM     echo Method 3: Direct execution >> "%LOG_FILE%"
    @REM     "%APP_SUPPORT%\power_monitor.exe" > "%LOG_DIR%\output3.log" 2> "%LOG_DIR%\error3.log"
        
    @REM     echo --- Method 3 Error Log ---
    @REM     if exist "%LOG_DIR%\error3.log" (
    @REM         type "%LOG_DIR%\error3.log"
    @REM         type "%LOG_DIR%\error3.log" >> "%LOG_FILE%"
    @REM     )
    @REM     if exist "%LOG_DIR%\output3.log" (
    @REM         type "%LOG_DIR%\output3.log"
    @REM         type "%LOG_DIR%\output3.log" >> "%LOG_FILE%"
    @REM     )
        
    @REM     echo × Failed to start PowerMonitor with all methods
    @REM     echo Failed to start PowerMonitor with all methods >> "%LOG_FILE%"
        
        echo --- PowerMonitor Log ---
        if exist "%LOG_DIR%\power_monitor.log" (
            type "%LOG_DIR%\power_monitor.log"
            type "%LOG_DIR%\power_monitor.log" >> "%LOG_FILE%"
        )
        
        echo --- Process List ---
        tasklist >> "%LOG_FILE%"
        
        echo --- File Permissions ---
        icacls "%APP_SUPPORT%\PowerMonitor.exe" >> "%LOG_FILE%"
        
        echo --- Directory Contents ---
        dir "%APP_SUPPORT%" >> "%LOG_FILE%"
        
        exit /b 1
    )
)

:: Check prerequisites
ver | find "10." >nul || (
    echo Windows 10 or later required
    echo Windows 10 or later required >> "%LOG_FILE%"
    exit /b 1
)

echo Installation completed successfully
echo Installation completed successfully at %date% %time% >> "%LOG_FILE%"
exit /b 0 