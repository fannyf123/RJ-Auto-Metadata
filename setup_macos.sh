#!/bin/bash
# One-command setup script for RJ Auto Metadata on macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/riiicil/RJ-Auto-Metadata/main/setup_macos.sh | bash
# Or: chmod +x setup_macos.sh && ./setup_macos.sh

set -e 

echo "🍎 RJ Auto Metadata - macOS One-Command Setup"
echo "=============================================="

if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

macos_version=$(sw_vers -productVersion)
macos_major=$(echo "$macos_version" | cut -d. -f1)
macos_minor=$(echo "$macos_version" | cut -d. -f2)

echo "📋 System Information:"
echo "  - macOS Version: $macos_version"
echo "  - Architecture: $(uname -m)"

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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

add_to_path() {
    local path_to_add="$1"
    local shell_profile=""
    
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_profile="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        shell_profile="$HOME/.bash_profile"
    else
        shell_profile="$HOME/.profile"
    fi
    
    if [[ ":$PATH:" != *":$path_to_add:"* ]]; then
        echo "export PATH=\"$path_to_add:\$PATH\"" >> "$shell_profile"
        export PATH="$path_to_add:$PATH"
        echo "  ✅ Added $path_to_add to PATH in $shell_profile"
    fi
}

if ! command_exists xcode-select || ! xcode-select -p &>/dev/null; then
    echo "📱 Installing Xcode Command Line Tools..."
    echo "   A dialog will appear - click 'Install' and wait for completion."
    xcode-select --install
    echo "   Please wait for Command Line Tools installation to complete, then re-run this script."
    exit 0
else
    echo "✅ Xcode Command Line Tools already installed"
fi

if ! command_exists brew; then
    echo ""
    echo "🍺 Homebrew not found. Installing Homebrew..."
    echo "   This may take several minutes..."
    
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    if [[ $(uname -m) == "arm64" ]]; then
        # Apple Silicon
        add_to_path "/opt/homebrew/bin"
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        add_to_path "/usr/local/bin"
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    echo "✅ Homebrew installed successfully!"
else
    brew_version=$(brew --version | head -1)
    echo "✅ Homebrew found: $brew_version"
    
    if [[ $(uname -m) == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    else
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
    fi
fi

echo ""
echo "🔄 Updating Homebrew..."
brew update || echo "⚠️ Homebrew update failed, continuing..."

echo ""
echo "🐍 Checking Python installation..."
python_gui_compatible=false

if command_exists python3; then
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    python_path=$(which python3)
    
    echo "  📍 Found Python $python_version at: $python_path"
    
    if [[ "$python_path" == *"/Library/Frameworks/Python.framework"* ]] || [[ "$python_path" == *"/usr/bin/python3"* ]]; then
        echo "  ✅ Python appears to be GUI-compatible (Framework build)"
        python_gui_compatible=true
    else
        echo "  ⚠️ Python from Homebrew detected - may have GUI issues"
        echo "     CustomTkinter requires Framework Python for proper GUI rendering"
    fi
else
    echo "  ❌ Python 3 not found"
fi

if [[ "$python_gui_compatible" != true ]]; then
    echo ""
    echo "🔧 GUI Compatibility Fix Required:"
    echo "   For proper GUI functionality, please install Python from python.org"
    echo "   This ensures CustomTkinter works correctly on macOS."
    echo ""
    echo "📥 Downloading Python installer..."
    
    if [[ $(uname -m) == "arm64" ]]; then
        python_installer_url="https://www.python.org/ftp/python/3.12.5/python-3.12.5-macos11.pkg"
        echo "  🔽 Apple Silicon detected - downloading Universal installer"
    else
        python_installer_url="https://www.python.org/ftp/python/3.12.5/python-3.12.5-macos10.9.pkg"
        echo "  🔽 Intel Mac detected - downloading Intel installer"
    fi
    
    curl -L -o python_installer.pkg "$python_installer_url"
    
    echo ""
    echo "📦 Please install Python manually:"
    echo "   1. Double-click: python_installer.pkg"
    echo "   2. Follow the installation wizard"
    echo "   3. ⚠️ IMPORTANT: Select 'Add Python to PATH' if prompted"
    echo "   4. After installation, re-run this setup script"
    echo ""
    echo "🔄 After Python installation, run:"
    echo "   curl -fsSL https://raw.githubusercontent.com/riiicil/RJ-Auto-Metadata/main/setup_macos.sh | bash"
    echo ""
    
    if command_exists open; then
        echo "🚀 Opening installer..."
        open python_installer.pkg
    fi
    
    echo "Setup paused. Please install Python and re-run this script."
    exit 0
fi

echo ""
echo "🔧 Installing external tools..."
echo "   This may take 10-15 minutes depending on your internet connection..."

essential_tools=(
    "ghostscript"
    "ffmpeg"
    "exiftool"
    "cairo"
    "pango"
    "gdk-pixbuf"
    "librsvg"
    "pkg-config"
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
    echo "  ✅ Base requirements installed successfully"
else
    echo "  ⚠️ Some dependencies failed to install. Trying individual installation..."
    
    # Try installing problematic packages individually
    problematic_packages=("cairocffi" "cairosvg")
    for pkg in "${problematic_packages[@]}"; do
        echo "  📦 Trying to install $pkg..."
        python3 -m pip install --no-cache-dir "$pkg" || echo "    ❌ $pkg failed"
    done
    
    # Try installing requirements again
    python3 -m pip install -r requirements.txt || echo "    ⚠️ Some packages may still be missing"
fi
echo "  📦 Installing additional macOS dependencies..."
additional_packages=(
    "Flask-SQLAlchemy"
    "Pillow"
    "svglib"
    "reportlab"
    "cairocffi"
    "requests"
    "google-genai" 
    "portalocker"
    "CairoSVG"
    "customtkinter"
    "setuptools"
)

for pkg in "${additional_packages[@]}"; do
    echo "  📦 Installing $pkg..."
    python3 -m pip install "$pkg" || echo "    ⚠️ $pkg installation failed"
done

echo "  ✅ Python dependencies installation completed"
echo ""
echo "🧪 Running cross-platform compatibility test..."
if python3 test_cross_platform.py; then
    echo "  🎉 Compatibility test PASSED!"
else
    echo "  ⚠️ Compatibility test had issues, but app may still work"
fi

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

echo ""
echo "🎉 Setup completed!"
echo "=============================================="
echo "📁 Project location: $project_dir"
echo ""

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
echo "   - Full Manual: cat README.md"
echo ""
echo "Happy processing! 🎨"
