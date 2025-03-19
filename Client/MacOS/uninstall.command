#!/bin/bash
cd "$(dirname "$0")"
./uninstall.sh

(sleep 2; osascript -e 'tell application "Terminal" to close (every window whose name contains "uninstall.command")') &
exit 0