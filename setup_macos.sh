#!/bin/bash
# One-command setup script for RJ Auto Metadata on macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/riiicil/RJ-Auto-Metadata/main/setup_macos.sh | bash
# Or: chmod +x setup_macos.sh && ./setup_macos.sh

set -e  # Exit on any error

echo "🍎 RJ Auto Metadata - macOS One-Command Setup"
echo "=============================================="

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Check macOS version
macos_version=$(sw_vers -productVersion)
macos_major=$(echo "$macos_version" | cut -d. -f1)
macos_minor=$(echo "$macos_version" | cut -d. -f2)

echo "📋 System Information:"
echo "  - macOS Version: $macos_version"
echo "  - Architecture: $(uname -m)"

# Check macOS compatibility
if [[ $macos_major -lt 10 ]] || [[ $macos_major -eq 10 && $macos_minor -lt 14 ]]; then
    echo "⚠️  WARNING: macOS $macos_version is quite old."
    echo "   Recommended: macOS 10.14 (Mojave) or newer"
    echo "   Some features may not work properly."
    echo ""
    read -p "Do you want to continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to add to PATH
add_to_path() {
    local path_to_add="$1"
    local shell_profile=""
    
    # Detect shell and profile file
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_profile="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        shell_profile="$HOME/.bash_profile"
    else
        shell_profile="$HOME/.profile"
    fi
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$path_to_add:"* ]]; then
        echo "export PATH=\"$path_to_add:\$PATH\"" >> "$shell_profile"
        export PATH="$path_to_add:$PATH"
        echo "  ✅ Added $path_to_add to PATH in $shell_profile"
    fi
}

# Install Xcode Command Line Tools if needed
if ! command_exists xcode-select || ! xcode-select -p &>/dev/null; then
    echo "📱 Installing Xcode Command Line Tools..."
    echo "   A dialog will appear - click 'Install' and wait for completion."
    xcode-select --install
    echo "   Please wait for Command Line Tools installation to complete, then re-run this script."
    exit 0
else
    echo "✅ Xcode Command Line Tools already installed"
fi

# Check if Homebrew is installed
if ! command_exists brew; then
    echo ""
    echo "🍺 Homebrew not found. Installing Homebrew..."
    echo "   This may take several minutes..."
    
    # Install Homebrew
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH based on architecture
    if [[ $(uname -m) == "arm64" ]]; then
        # Apple Silicon
        add_to_path "/opt/homebrew/bin"
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        # Intel Mac
        add_to_path "/usr/local/bin"
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    echo "✅ Homebrew installed successfully!"
else
    brew_version=$(brew --version | head -1)
    echo "✅ Homebrew found: $brew_version"
    
    # Ensure Homebrew paths are set
    if [[ $(uname -m) == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    else
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
    fi
fi

# Update Homebrew
echo ""
echo "🔄 Updating Homebrew..."
brew update || echo "⚠️ Homebrew update failed, continuing..."

# Install Python if needed
echo ""
echo "🐍 Checking Python installation..."
if command_exists python3; then
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    python_major=$(echo "$python_version" | cut -d. -f1)
    python_minor=$(echo "$python_version" | cut -d. -f2)
    
    if [[ $python_major -eq 3 && $python_minor -ge 9 ]]; then
        echo "  ✅ Python $python_version is compatible"
    else
        echo "  ⚠️ Python $python_version may not be fully compatible (3.9+ recommended)"
        echo "  Installing Python 3.11 via Homebrew..."
        brew install python@3.11
        add_to_path "$(brew --prefix python@3.11)/bin"
    fi
else
    echo "  📦 Installing Python 3.11..."
    brew install python@3.11
    add_to_path "$(brew --prefix python@3.11)/bin"
fi

# Install external tools
echo ""
echo "🔧 Installing external tools..."
echo "   This may take 10-15 minutes depending on your internet connection..."

# Essential tools for RJ Auto Metadata
essential_tools=(
    "ghostscript"      # For AI/EPS vector processing
    "ffmpeg"          # For video processing  
    "exiftool"        # For metadata writing
    "cairo"           # For SVG rendering
    "pango"           # For text rendering in SVG
    "gdk-pixbuf"      # For image loading in SVG
    "librsvg"         # For SVG processing
    "pkg-config"      # For building native extensions
)

failed_installs=()

for tool in "${essential_tools[@]}"; do
    if brew list "$tool" &>/dev/null; then
        echo "  ✅ $tool already installed"
    else
        echo "  📦 Installing $tool..."
        if brew install "$tool"; then
            echo "  ✅ $tool installed successfully"
        else
            echo "  ❌ Failed to install $tool"
            failed_installs+=("$tool")
        fi
    fi
done

# Report failed installations
if [[ ${#failed_installs[@]} -gt 0 ]]; then
    echo ""
    echo "⚠️ Some tools failed to install: ${failed_installs[*]}"
    echo "   You may need to install them manually later."
    echo "   The app may still work for basic file types."
fi

# Get source code if we're not already in the project directory
echo ""
if [[ -f "main.py" && -f "requirements.txt" ]]; then
    echo "✅ Already in RJ Auto Metadata project directory"
    project_dir=$(pwd)
else
    echo "📥 Downloading RJ Auto Metadata source code..."
    if command_exists git; then
        git clone https://github.com/riiicil/RJ-Auto-Metadata.git
        project_dir="$(pwd)/RJ-Auto-Metadata"
    else
        echo "   Git not found, downloading ZIP..."
        curl -L -o rj-auto-metadata.zip https://github.com/riiicil/RJ-Auto-Metadata/archive/main.zip
        unzip -q rj-auto-metadata.zip
        mv RJ-Auto-Metadata-main RJ-Auto-Metadata
        project_dir="$(pwd)/RJ-Auto-Metadata"
        rm rj-auto-metadata.zip
    fi
    cd "$project_dir"
    echo "  ✅ Source code downloaded to: $project_dir"
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
echo "   This may take a few minutes..."

# Upgrade pip first
python3 -m pip install --upgrade pip

# Install requirements with some retry logic
if python3 -m pip install -r requirements.txt; then
    echo "  ✅ Python dependencies installed successfully"
else
    echo "  ⚠️ Some dependencies failed to install. Trying individual installation..."
    
    # Try installing problematic packages individually
    problematic_packages=("cairocffi" "cairosvg")
    for pkg in "${problematic_packages[@]}"; do
        echo "  � Trying to install $pkg..."
        python3 -m pip install --no-cache-dir "$pkg" || echo "    ❌ $pkg failed"
    done
    
    # Try installing requirements again
    python3 -m pip install -r requirements.txt || echo "    ⚠️ Some packages may still be missing"
fi

# Run compatibility test
echo ""
echo "🧪 Running cross-platform compatibility test..."
if python3 test_cross_platform.py; then
    echo "  🎉 Compatibility test PASSED!"
else
    echo "  ⚠️ Compatibility test had issues, but app may still work"
fi

# Verify external tools
echo ""
echo "🔍 Verifying external tools..."
tools_status=()

if command_exists gs; then
    gs_version=$(gs --version 2>/dev/null | head -1)
    echo "  ✅ Ghostscript: $gs_version"
    tools_status+=("gs:ok")
else
    echo "  ❌ Ghostscript not found"
    tools_status+=("gs:missing")
fi

if command_exists ffmpeg; then
    ffmpeg_version=$(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f3)
    echo "  ✅ FFmpeg: $ffmpeg_version"
    tools_status+=("ffmpeg:ok")
else
    echo "  ❌ FFmpeg not found"
    tools_status+=("ffmpeg:missing")
fi

if command_exists exiftool; then
    exiftool_version=$(exiftool -ver 2>/dev/null)
    echo "  ✅ ExifTool: $exiftool_version"
    tools_status+=("exiftool:ok")
else
    echo "  ❌ ExifTool not found"
    tools_status+=("exiftool:missing")
fi

# Test SVG capabilities
echo "  🧪 Testing SVG processing..."
python3 -c "
import sys
try:
    import cairosvg
    print('  ✅ CairoSVG available')
except ImportError:
    print('  ❌ CairoSVG not available')

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    print('  ✅ svglib + reportlab available')
except ImportError:
    print('  ❌ svglib/reportlab not available')
" 2>/dev/null

# Create run script
echo ""
echo "📝 Creating run script..."
cat > run_app.sh << 'EOF'
#!/bin/bash
# Quick run script for RJ Auto Metadata
echo "🚀 Starting RJ Auto Metadata..."

# Set up environment
if [[ $(uname -m) == "arm64" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
else
    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
fi

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    echo "❌ Please run this script from the RJ Auto Metadata directory"
    exit 1
fi

# Run the application
python3 main.py
EOF

chmod +x run_app.sh

# Final setup report
echo ""
echo "🎉 Setup completed!"
echo "=============================================="
echo "📁 Project location: $project_dir"
echo ""

# Count successful tools
successful_tools=0
for status in "${tools_status[@]}"; do
    if [[ "$status" == *":ok" ]]; then
        ((successful_tools++))
    fi
done

echo "📊 Setup Summary:"
echo "  ✅ External tools working: $successful_tools/3"
echo "  📦 Python dependencies: Installed"
echo "  🧪 Compatibility test: Run"
echo ""

if [[ $successful_tools -eq 3 ]]; then
    echo "🟢 EXCELLENT! All tools are working."
    echo "   You can process all file types: Images, Videos, Vectors"
elif [[ $successful_tools -ge 1 ]]; then
    echo "🟡 GOOD! Most tools are working."
    echo "   Some file types may not process correctly."
else
    echo "🔴 WARNING! External tools may be missing."
    echo "   Only basic image processing may work."
fi

echo ""
echo "🚀 To run RJ Auto Metadata:"
echo "   cd $project_dir"
echo "   ./run_app.sh"
echo ""
echo "📚 For help:"
echo "   - Quick Guide: cat QUICK_START_GUIDE.md"
echo "   - macOS Guide: cat README_macOS.md"
echo "   - Full Manual: cat README.md"
echo ""
echo "🔧 If you have SVG issues, run: ./fix_svg_macos.sh"
echo ""
echo "Happy processing! 🎨"
