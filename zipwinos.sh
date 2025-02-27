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

# Clean up previous Windows builds only
rm -rf Client/Windows/build Client/Windows/dist *.pyc
rm -rf Client/Windows/*.egg-info
rm -rf Client/Windows/__pycache__
rm -rf ~/Library/Caches/com.apple.python/
rm -rf ~/Library/Caches/pip

# Install Windows dependencies
pip3 install --use-pep517 requests

# Create distwin directory
mkdir -p distwin

# Build power monitor
cd Client/Windows && \
mkdir -p dist && \
pyinstaller power_monitor.spec \
          --distpath ./dist \
          --workpath ./build && \
pyinstaller --clean \
          --name AttendanceTracker \
          --onefile \
          --add-data "config.json:." \
          --hidden-import win32api \
          --hidden-import win32con \
          --hidden-import win32event \
          --hidden-import win32service \
          --hidden-import win32serviceutil \
          --hidden-import win32com.client \
          --distpath ./dist \
          --workpath ./build \
          AttendanceTracker.py && \
cd ../..

# Wait for build to complete and check success
if [ ! -f "Client/Windows/dist/power_monitor" ]; then
    echo "❌ Failed to build power monitor"
    exit 1
fi

# Wait for app build and check success
if [ ! -f "Client/Windows/dist/AttendanceTracker" ]; then
    echo "❌ Failed to build AttendanceTracker"
    exit 1
fi

echo "✅ Windows executables built successfully"

# Prepare package directory
mkdir -p distwin/package

# Copy files to distribution
cp Client/Windows/dist/power_monitor distwin/package/power_monitor.exe || { echo "❌ Failed to copy power monitor"; exit 1; }
cp Client/Windows/dist/AttendanceTracker distwin/package/AttendanceTracker.exe || { echo "❌ Failed to copy AttendanceTracker"; exit 1; }
cp Client/Windows/config.json distwin/package/ || { echo "❌ Failed to copy config"; exit 1; }
cp Client/Windows/test_install.bat distwin/package/ || { echo "❌ Failed to copy install script"; exit 1; }
cp Client/Windows/uninstall.bat distwin/package/ || { echo "❌ Failed to copy uninstall script"; exit 1; }

echo "✅ Windows package prepared successfully"

# Create zip
echo "Creating zip package..."
cd distwin
zip -r AttendanceTracker_Windows.zip package/
cd ..

echo "✅ AttendanceTracker_Windows.zip created successfully" 