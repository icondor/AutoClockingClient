#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Set up logging
LOG_DIR="$HOME/Library/Logs/AttendanceTracker"
LOG_FILE="$LOG_DIR/installation.log"
mkdir -p "$LOG_DIR"

# Logging function
log() {
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp: $message" >> "$LOG_FILE"
    echo -e "$message"
}

# Application directories
APP_SUPPORT_DIR="${HOME}/Library/Application Support/AttendanceTracker"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
SCRIPTS_DIR="${APP_SUPPORT_DIR}/scripts"

# Create necessary directories
mkdir -p "${APP_SUPPORT_DIR}" "${SCRIPTS_DIR}"

# Create log files
touch "${APP_SUPPORT_DIR}/error.log" "${APP_SUPPORT_DIR}/output.log"
chmod 644 "${APP_SUPPORT_DIR}/error.log" "${APP_SUPPORT_DIR}/output.log"

# Remove any existing app installation
log "Removing any existing installation..."

# Kill any existing power_monitor processes
log "Killing any existing power_monitor processes..."
pkill -9 -f power_monitor || true
sleep 2  # Wait for processes to be killed

rm -rf "${APP_SUPPORT_DIR}/AttendanceTracker.app"

# Copy the built app and config
log "Copying app from $(pwd)/AttendanceTracker.app to ${APP_SUPPORT_DIR}/"
ditto "./AttendanceTracker.app" "${APP_SUPPORT_DIR}/AttendanceTracker.app" || { log "❌ Failed to copy app"; exit 1; }
cp ./power_monitor "${APP_SUPPORT_DIR}/" || { log "❌ Failed to copy power monitor"; exit 1; }

# Copy config file
log "Copying config file..."
cp "./config.json" "${APP_SUPPORT_DIR}/" || { log "❌ Failed to copy config file"; exit 1; }

# Create PowerMonitor.app wrapper
log "Creating PowerMonitor.app wrapper..."
POWERMONITOR_APP="${APP_SUPPORT_DIR}/PowerMonitor.app"
MACOS_DIR="${POWERMONITOR_APP}/Contents/MacOS"
mkdir -p "$MACOS_DIR"

# Create Info.plist
mkdir -p "${POWERMONITOR_APP}/Contents"
cat > "${POWERMONITOR_APP}/Contents/Info.plist" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PowerMonitor</string>
    <key>CFBundleIdentifier</key>
    <string>com.company.powermonitor</string>
    <key>CFBundleName</key>
    <string>PowerMonitor</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSBackgroundOnly</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOL

# Create launcher script
cat > "${MACOS_DIR}/PowerMonitor" << EOL
#!/bin/bash
cd "${APP_SUPPORT_DIR}"
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="${HOME}"
export DEBUG=1
"${APP_SUPPORT_DIR}/power_monitor" &> "${APP_SUPPORT_DIR}/output.log" &
EOL
chmod +x "${MACOS_DIR}/PowerMonitor"

# Remove any existing login items first
osascript << EOL
tell application "System Events"
    set loginItems to get every login item
    repeat with theItem in loginItems
        if (path of theItem contains "AttendanceTracker") or (path of theItem contains "PowerMonitor") then
            delete theItem
        end if
    end repeat
end tell
EOL

# Add to Login Items (using the app bundle)
log "Adding login item..."
osascript -e "tell application \"System Events\" to make new login item at end with properties {path:\"${POWERMONITOR_APP}\", hidden:true}" || { log "❌ Failed to add login item"; exit 1; }

# Verify login item
login_item=$(osascript << EOL
tell application "System Events"
    set itemNames to get the name of every login item
    return itemNames as string
end tell
EOL
)

if echo "$login_item" | grep -q "PowerMonitor"; then
    log "✅ Login item PowerMonitor found"
else
    log "❌ Login item not found"
    exit 1
fi

log "Power monitor installed at: ${APP_SUPPORT_DIR}/power_monitor"
log "Wrapper app created at: ${POWERMONITOR_APP}"
log "Logs will be available at: ${APP_SUPPORT_DIR}/error.log and output.log"

log "Installation completed successfully!"

# Start PowerMonitor right away
log "Starting PowerMonitor..."
open "${POWERMONITOR_APP}" || { log "❌ Failed to start PowerMonitor"; exit 1; }

# Give it a moment to start
sleep 2

# Verify it's running
if pgrep -f power_monitor > /dev/null; then
    log "✅ PowerMonitor is now running"
else
    log "⚠️ PowerMonitor didn't start automatically. It will start on next login."
fi