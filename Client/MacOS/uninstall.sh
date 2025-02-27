#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Log directory
LOG_DIR="${HOME}/Library/Logs/AttendanceTracker"

# Logging function
log() {
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Try to create log directory if it doesn't exist
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR" 2>/dev/null || true
    fi
    
    # Write to log file or fallback to /tmp
    if [ -d "$LOG_DIR" ]; then
        echo "$timestamp: $message" >> "${LOG_DIR}/uninstallation.log" 2>/dev/null || echo "$timestamp: $message" >> "/tmp/AttendanceTracker_uninstall.log"
    else
        echo "$timestamp: $message" >> "/tmp/AttendanceTracker_uninstall.log"
    fi
    
    echo -e "$message"
}

log "Uninstalling AttendanceTracker..."

# Kill any running processes
log "Killing running processes..."
pkill -9 -f power_monitor || true
pkill -9 -f PowerMonitor || true
pkill -9 -f AttendanceTracker || true
sleep 2  # Wait for processes to terminate

# Remove from Login Items
log "Removing from Login Items..."
osascript -e '
    tell application "System Events"
        delete (every login item whose path contains "PowerMonitor.app")
    end tell' || log "${YELLOW}⚠️ Failed to remove Login Item - may require manual removal${NC}"

# Remove LaunchAgent if it exists (from prior installs)
LAUNCH_AGENT="${HOME}/Library/LaunchAgents/com.company.attendancetracker.plist"
if [ -f "$LAUNCH_AGENT" ]; then
    log "Removing LaunchAgent..."
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null
    rm -f "$LAUNCH_AGENT" || log "${YELLOW}⚠️ Failed to remove LaunchAgent - may require sudo${NC}"
fi

# Remove all installed files
log "Removing installed files..."
rm -rf "${HOME}/Library/Application Support/AttendanceTracker" || log "${YELLOW}⚠️ Failed to remove Application Support files - may require sudo${NC}"
rm -rf "${HOME}/Library/Logs/AttendanceTracker" || log "${YELLOW}⚠️ Failed to remove Logs - may require sudo${NC}"

log "${GREEN}✅ AttendanceTracker has been uninstalled${NC}"