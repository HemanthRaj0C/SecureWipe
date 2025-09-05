#!/bin/bash
#
# Secure Wipe GUI Launcher
# 
# This script properly launches the GUI with root privileges and X11 access.
# It handles the common "Authorization required" error when using sudo with GUI apps.
#

set -e  # Exit on any error

echo "🔒 Secure Wipe Tool - GUI Launcher"
echo "=================================="

# Check if we're already running as root
if [[ $EUID -eq 0 ]]; then
    echo "✅ Already running as root. Starting GUI..."
    cd "$(dirname "$0")"
    python3 gui.py
    exit 0
fi

echo "🔧 Setting up GUI with root privileges..."

# Check if GUI file exists
if [[ ! -f "$(dirname "$0")/gui.py" ]]; then
    echo "❌ Error: gui.py not found in $(dirname "$0")"
    echo "   Make sure you're running this script from the secure_wipe directory."
    exit 1
fi

# Check if DISPLAY is set
if [[ -z "$DISPLAY" ]]; then
    echo "❌ Error: No DISPLAY environment variable found."
    echo "   GUI applications require a display server."
    exit 1
fi

# Grant X11 access to root user
echo "🔓 Granting X11 display access to root..."
if xhost +local:root >/dev/null 2>&1; then
    echo "✅ X11 access granted successfully"
else
    echo "⚠️  Warning: Could not grant X11 access."
    echo "   GUI may not work properly."
fi

# Change to script directory
cd "$(dirname "$0")"

# Launch GUI with proper environment
echo "🚀 Launching Secure Wipe GUI..."
echo "   (You may be prompted for your password)"

if sudo -E DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" python3 gui.py; then
    echo "✅ GUI closed successfully"
else
    echo "❌ GUI exited with error"
fi

# Clean up X11 access
echo "🧹 Cleaning up X11 permissions..."
if xhost -local:root >/dev/null 2>&1; then
    echo "✅ X11 access revoked"
else
    echo "⚠️  Could not revoke X11 access (this is usually harmless)"
fi

echo "👋 Done!"
