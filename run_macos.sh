#!/bin/bash
# Quick run script for RJ Auto Metadata on macOS
# Usage: ./run_macos.sh

echo "🍎 Starting RJ Auto Metadata on macOS..."

# Set up Homebrew environment
if [[ $(uname -m) == "arm64" ]]; then
    # Apple Silicon Mac
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
else
    # Intel Mac
    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
fi

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    echo "❌ Error: main.py not found!"
    echo "   Please run this script from the RJ Auto Metadata directory."
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found!"
    echo "   Please install Python 3.9+ or run the setup script:"
    echo "   ./setup_macos.sh"
    exit 1
fi

# Quick dependency check
if ! python3 -c "import customtkinter" &>/dev/null; then
    echo "⚠️ Dependencies not installed or incomplete."
    echo "🔄 Installing dependencies..."
    pip3 install -r requirements.txt || {
        echo "❌ Failed to install dependencies."
        echo "   Please run the full setup script: ./setup_macos.sh"
        exit 1
    }
fi

# Check virtual environment preference
if [[ -d "venv" ]]; then
    echo "📦 Virtual environment detected, activating..."
    source venv/bin/activate
fi

# Quick system check
echo "🔍 Quick system check..."
tools_ok=0
total_tools=3

if command -v gs >/dev/null 2>&1; then
    echo "  ✅ Ghostscript available"
    ((tools_ok++))
else
    echo "  ❌ Ghostscript not found (vector files may not work)"
fi

if command -v ffmpeg >/dev/null 2>&1; then
    echo "  ✅ FFmpeg available"
    ((tools_ok++))
else
    echo "  ❌ FFmpeg not found (video files may not work)"
fi

if command -v exiftool >/dev/null 2>&1; then
    echo "  ✅ ExifTool available"
    ((tools_ok++))
else
    echo "  ❌ ExifTool not found (metadata writing may not work)"
fi

if [[ $tools_ok -eq $total_tools ]]; then
    echo "🟢 All external tools ready! ($tools_ok/$total_tools)"
elif [[ $tools_ok -gt 0 ]]; then
    echo "🟡 Some tools missing ($tools_ok/$total_tools) - basic functionality available"
else
    echo "🔴 No external tools found! Only basic image processing will work."
    echo "   Run setup script to install tools: ./setup_macos.sh"
fi

# Launch the application
echo ""
echo "🚀 Launching RJ Auto Metadata..."
echo "   Close this terminal to stop the application"
echo ""

python3 main.py

echo ""
echo "👋 Application closed. Thanks for using RJ Auto Metadata!"
