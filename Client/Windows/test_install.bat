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
mkdir "%APP_SUPPORT%" 2>nul
mkdir "%LOG_DIR%" 2>nul

:: Create log file
set "LOG_FILE=%LOG_DIR%\install.log"
echo Installation started at %date% %time% > "%LOG_FILE%"
echo Current directory: %CURRENT_DIR% >> "%LOG_FILE%"
echo Target directory: %APP_SUPPORT% >> "%LOG_FILE%"

:: Kill any existing processes
echo Stopping existing processes...
taskkill /F /IM "power_monitor.exe" 2>>"%LOG_FILE%" || echo No existing power_monitor process found >> "%LOG_FILE%"
taskkill /F /IM "AttendanceTracker.exe" 2>>"%LOG_FILE%" || echo No existing AttendanceTracker process found >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul

:: Copy files with full paths
echo Copying files...
echo Copying from %CURRENT_DIR% to %APP_SUPPORT% >> "%LOG_FILE%"
xcopy /Y /F "%CURRENT_DIR%AttendanceTracker.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y /F "%CURRENT_DIR%power_monitor.exe" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1
xcopy /Y /F "%CURRENT_DIR%config.json" "%APP_SUPPORT%\" >>"%LOG_FILE%" 2>&1

:: Verify files were copied
if not exist "%APP_SUPPORT%\power_monitor.exe" (
    echo Error: power_monitor.exe not found in target directory >> "%LOG_FILE%"
    echo Error: power_monitor.exe not found in target directory
    exit /b 1
)

:: Create startup shortcut with full path
echo Creating startup entry...
(
    echo @echo off
    echo cd /d "%APP_SUPPORT%"
    echo start "" "%APP_SUPPORT%\power_monitor.exe"
) > "%STARTUP_DIR%\AttendanceTracker_PowerMonitor.bat"
echo Created startup entry >> "%LOG_FILE%"

:: Start the monitor with full path and error capture
echo Starting PowerMonitor...
cd /d "%APP_SUPPORT%"
echo Current directory before start: %CD% >> "%LOG_FILE%"
echo Attempting to start power_monitor.exe... >> "%LOG_FILE%"

:: Try method 1: Direct start with error capture
echo Method 1: Direct start >> "%LOG_FILE%"
start "" "%APP_SUPPORT%\power_monitor.exe" 2>> "%LOG_FILE%"

:: Verify installation with proper delay
timeout /t 3 /nobreak >nul
tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
if !errorlevel! equ 0 (
    echo ✓ PowerMonitor is running
    echo PowerMonitor started successfully >> "%LOG_FILE%"
) else (
    echo × Failed to start PowerMonitor, trying alternative method...
    echo Failed to start PowerMonitor, trying method 2... >> "%LOG_FILE%"
    
    :: Try method 2: CMD call with error capture
    echo Method 2: CMD call >> "%LOG_FILE%"
    cmd /c "%APP_SUPPORT%\power_monitor.exe" 2>> "%LOG_FILE%"
    timeout /t 3 /nobreak >nul
    
    tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
    if !errorlevel! equ 0 (
        echo ✓ PowerMonitor started successfully with alternative method
        echo PowerMonitor started successfully with method 2 >> "%LOG_FILE%"
    ) else (
        echo × Failed with method 2, trying final method... >> "%LOG_FILE%"
        
        :: Try method 3: PowerShell with error capture
        echo Method 3: PowerShell >> "%LOG_FILE%"
        powershell -Command "& { $process = Start-Process -FilePath '%APP_SUPPORT%\power_monitor.exe' -WorkingDirectory '%APP_SUPPORT%' -PassThru -RedirectStandardError '%LOG_DIR%\error.log' -RedirectStandardOutput '%LOG_DIR%\output.log'; Write-Output $process.Id }" >> "%LOG_FILE%" 2>&1
        timeout /t 3 /nobreak >nul
        
        tasklist /FI "IMAGENAME eq power_monitor.exe" | find "power_monitor.exe" >nul
        if !errorlevel! equ 0 (
            echo ✓ PowerMonitor started successfully with final method
            echo PowerMonitor started successfully with method 3 >> "%LOG_FILE%"
        ) else (
            echo × Failed to start PowerMonitor with all methods
            echo Failed to start PowerMonitor with all methods >> "%LOG_FILE%"
            echo --- Installation Log ---
            type "%LOG_FILE%"
            echo --- Error Log ---
            if exist "%LOG_DIR%\error.log" type "%LOG_DIR%\error.log"
            echo --- Output Log ---
            if exist "%LOG_DIR%\output.log" type "%LOG_DIR%\output.log"
            echo --- Process List ---
            tasklist >> "%LOG_FILE%"
            tasklist
            echo --- Directory Contents ---
            dir "%APP_SUPPORT%" >> "%LOG_FILE%"
            dir "%APP_SUPPORT%"
            exit /b 1
        )
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