#!/bin/bash

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Make the install script executable and run it
chmod +x test_install.sh
./test_install.sh

# Verify installation
echo "Verifying installation..."
LOGIN_ITEMS=$(osascript -e 'tell application "System Events" to get the name of every login item')
echo "Current login items: $LOGIN_ITEMS"

(sleep 2; osascript -e 'tell application "Terminal" to close (every window whose name contains "start.command")') &
exit 0