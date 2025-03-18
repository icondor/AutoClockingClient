#!/bin/bash

# Ensure we're in the virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    if [ -d ".venv" ]; then
        echo "Activating virtual environment..."
        source .venv/bin/activate
    else
        echo "❌ Virtual environment not found. Please create and activate it first."
        echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
fi

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing pyinstaller..."
    pip install pyinstaller
fi

# Clean up previous builds
rm -rf build dist *.pyc
rm -rf *.egg-info
rm -rf __pycache__
rm -rf ~/Library/Caches/com.apple.python/
rm -rf ~/Library/Caches/pip

# Install dependencies
pip3 install --use-pep517 requests pyobjc
pip3 install --use-pep517 pyobjc-framework-Cocoa

# Create dist directory
mkdir -p dist

# Build power monitor
cd Client/MacOS && \
PYTHONPATH=../.. pyinstaller --noconfirm power_monitor.spec && cd ../..

# Wait for build to complete and check success
if [ ! -f "Client/MacOS/dist/power_monitor" ]; then
    echo "❌ Failed to build power monitor"
    exit 1
fi

# Build the app
echo "Building AttendanceTracker app..."
cd Client/MacOS && \
PYTHONPATH=../.. pyinstaller --clean \
            --noconfirm \
            --name AttendanceTracker \
            --windowed \
            --add-data "config.json:." \
            --log-level ERROR \
            --noconsole \
            --paths ../../.venv/lib/python3.12/site-packages \
            --osx-bundle-identifier "com.company.attendancetracker" \
            AttendanceTracker.py && \
cd ../..

# Wait for app build and check success
if [ ! -d "Client/MacOS/dist/AttendanceTracker.app" ]; then
    echo "❌ Failed to build AttendanceTracker app"
    exit 1
fi

echo "✅ App built successfully"

# Prepare package directory
mkdir -p dist/package

# Copy files to distribution
cp -R "Client/MacOS/dist/AttendanceTracker.app" "dist/package/" || { echo "❌ Failed to copy app bundle"; exit 1; }
cp Client/MacOS/dist/power_monitor dist/package/ || { echo "❌ Failed to copy power monitor"; exit 1; }
cp Client/MacOS/config.json dist/package/ || { echo "❌ Failed to copy config"; exit 1; }
cp Client/MacOS/test_install.sh dist/package/ || { echo "❌ Failed to copy install script"; exit 1; }
cp Client/MacOS/start.command dist/package/ || { echo "❌ Failed to copy start command"; exit 1; }
cp Client/MacOS/uninstall.sh dist/package/ || { echo "❌ Failed to copy uninstall script"; exit 1; }
cp Client/MacOS/uninstall.command dist/package/ || { echo "❌ Failed to copy uninstall command"; exit 1; }
cp Client/MacOS/logging.conf dist/package/ || { echo "❌ Failed to copy logging.conf"; exit 1; }

# Make scripts executable
chmod +x dist/package/start.command dist/package/test_install.sh dist/package/uninstall.sh dist/package/uninstall.command dist/package/power_monitor

echo "✅ Build completed successfully"

# Create zip
echo "Creating zip package..."
cd dist
zip -r AttendanceTracker.zip package/
cd ..

echo "✅ AttendanceTracker.zip created successfully"

# Show LaunchAgent status if installed
launchctl list | grep attendancetracker || echo "Note: LaunchAgent not currently loaded"