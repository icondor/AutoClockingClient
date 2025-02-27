# Attendance Tracker - Installation Guide

## Quick Installation

1. Double-click the downloaded ZIP file to extract it
2. Open the 'macOS' folder
3. Double-click 'start.command'

## First Run Note

When running for the first time, you might see a security warning:

1. Right-click (or Control-click) on 'start.command'
2. Select "Open" from the menu
3. Click "Open" in the security dialog
4. The installation will proceed automatically

## What Happens

1. A Terminal window will open
2. You'll see the installation progress with colored messages:
   - Green ✅ = Success
   - Red ❌ = Error
3. The window stays open until you press Enter

## Common Issues

1. "start.command" won't open:
   - Make sure you've extracted the ZIP file
   - Try right-click -> Open as described above
   - Ensure you're in the 'macOS' folder

2. "Permission denied":
   - Close all Terminal windows
   - Try again

3. "File not found":
   - Check that all files are present:
     - start.command
     - test_install.sh
     - config.json

## After Installation

After successful installation:
1. You'll see a green success message
2. The application will start automatically on next login
3. No further action needed

## Uninstall

To remove the installation:
1. Open Terminal
2. Navigate to the extracted folder
3. Run: `./test_install.sh --cleanup`

## Support

If you encounter any issues:
- Email: support@company.com
- Support hours: Mon-Fri, 9:00 - 17:00