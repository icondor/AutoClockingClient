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

# Keep terminal window open to see results
echo -e "\nPress Enter to close this window..."
read