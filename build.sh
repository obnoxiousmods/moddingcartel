#!/bin/bash
# Build script for creating moddingcartel executable on Linux/macOS

echo "============================================"
echo "Building moddingcartel executable"
echo "============================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.10 or later"
    exit 1
fi

echo "[1/4] Installing dependencies..."
# Note: Dependencies are reinstalled on each build to ensure clean environment
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller
python3 -m pip install -r requirements.txt

echo
echo "[2/4] Running PyInstaller..."
pyinstaller moddingcartel.spec

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed!"
    exit 1
fi

echo
echo "[3/4] Checking build output..."
if [ -f "dist/moddingcartel" ]; then
    echo "SUCCESS: moddingcartel executable created!"
    echo "Location: dist/moddingcartel"
    chmod +x dist/moddingcartel
else
    echo "ERROR: moddingcartel executable was not created"
    exit 1
fi

echo
echo "[4/4] Build complete!"
echo
echo "The executable is located at: dist/moddingcartel"
echo "You can now distribute this single executable file."
echo
