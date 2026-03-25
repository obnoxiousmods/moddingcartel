#!/bin/bash
# Build script for creating moddingcartel executable on Linux/macOS

echo "============================================"
echo "Building moddingcartel executable"
echo "============================================"
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed or not in PATH"
    echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "[1/4] Installing dependencies..."
uv sync --group dev

echo
echo "[2/4] Running PyInstaller..."
uv run pyinstaller moddingcartel.spec

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
