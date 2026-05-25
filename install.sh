#!/bin/bash
# ============================================================================
# Elitza Agent Installer
# ============================================================================
# One-liner install:
#   curl -fsSL https://elitza.life/install.sh | bash
#
# Or with options:
#   curl -fsSL https://elitza.life/install.sh | bash -s -- --no-setup
#
# This script:
# 1. Installs uv (Python package manager) if not present
# 2. Clones elitza-agent repo to ~/.elitza/agent/
# 3. Creates a Python 3.11 virtual environment
# 4. Installs elitza-agent and all dependencies
# 5. Adds 'elitza' to PATH via ~/.local/bin
# 6. Runs 'elitza setup' wizard (unless --no-setup)
# ============================================================================

set -e

# Guard against environment leakage
if [ -n "${PYTHONPATH:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONPATH during install"
    unset PYTHONPATH
fi
if [ -n "${PYTHONHOME:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONHOME during install"
    unset PYTHONHOME
fi

export UV_NO_CONFIG=1

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
REPO_URL="https://github.com/dario-cositore/elitza-agent.git"
INSTALL_DIR="${ELITZA_INSTALL_DIR:-$HOME/.elitza/agent}"
ELITZA_HOME="${ELITZA_HOME:-$HOME/.elitza}"
PYTHON_VERSION="3.11"

# Options
RUN_SETUP=true

# Parse args
for arg in "$@"; do
    case "$arg" in
        --no-setup) RUN_SETUP=false ;;
        --help|-h)
            echo "Usage: curl -fsSL https://elitza.life/install.sh | bash -s -- [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-setup    Skip the setup wizard after install"
            echo "  --help, -h    Show this help"
            exit 0
            ;;
    esac
done

# Detect non-interactive mode
NON_INTERACTIVE=false
if [ ! -t 0 ]; then
    NON_INTERACTIVE=true
fi

echo ""
echo -e "${CYAN}${BOLD}⚡ Elitza Agent Installer${NC}"
echo ""

# ============================================================================
# Step 1: Install uv
# ============================================================================

echo -e "${CYAN}→${NC} Checking for uv..."

UV_CMD=""
if command -v uv &> /dev/null; then
    UV_CMD="uv"
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV_CMD="$HOME/.local/bin/uv"
elif [ -x "$HOME/.cargo/bin/uv" ]; then
    UV_CMD="$HOME/.cargo/bin/uv"
fi

if [ -n "$UV_CMD" ]; then
    UV_VERSION=$($UV_CMD --version 2>/dev/null)
    echo -e "${GREEN}✓${NC} uv found ($UV_VERSION)"
else
    echo -e "${CYAN}→${NC} Installing uv..."
    _uv_log="$(mktemp 2>/dev/null || echo "/tmp/elitza-uv-install.$$.log")"
    _uv_installer="$(mktemp 2>/dev/null || echo "/tmp/elitza-uv-installer.$$.sh")"

    if ! curl -LsSf https://astral.sh/uv/install.sh -o "$_uv_installer" 2>"$_uv_log"; then
        echo -e "${RED}✗${NC} Failed to download uv installer."
        sed 's/^/    /' "$_uv_log" >&2
        echo -e "${CYAN}→${NC} Install manually: https://docs.astral.sh/uv/"
        rm -f "$_uv_log" "$_uv_installer"
        exit 1
    fi

    if sh "$_uv_installer" >>"$_uv_log" 2>&1; then
        rm -f "$_uv_installer"
        if [ -x "$HOME/.local/bin/uv" ]; then
            UV_CMD="$HOME/.local/bin/uv"
        elif [ -x "$HOME/.cargo/bin/uv" ]; then
            UV_CMD="$HOME/.cargo/bin/uv"
        fi

        if [ -n "$UV_CMD" ]; then
            rm -f "$_uv_log"
            UV_VERSION=$($UV_CMD --version 2>/dev/null)
            echo -e "${GREEN}✓${NC} uv installed ($UV_VERSION)"
        else
            echo -e "${RED}✗${NC} uv installer reported success but binary not found."
            echo -e "${CYAN}→${NC} Add ~/.local/bin to PATH and retry."
            sed 's/^/    /' "$_uv_log" >&2
            rm -f "$_uv_log"
            exit 1
        fi
    else
        echo -e "${RED}✗${NC} Failed to install uv."
        sed 's/^/    /' "$_uv_log" >&2
        echo -e "${CYAN}→${NC} Install manually: https://docs.astral.sh/uv/"
        rm -f "$_uv_log" "$_uv_installer"
        exit 1
    fi
fi

# ============================================================================
# Step 2: Clone or update the repo
# ============================================================================

echo -e "${CYAN}→${NC} Installing Elitza Agent to ${INSTALL_DIR}..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${CYAN}→${NC} Existing install found, updating..."
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || {
        echo -e "${YELLOW}⚠${NC} git pull failed, reinstalling from scratch..."
        cd "$HOME"
        rm -rf "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR"
    }
else
    rm -rf "$INSTALL_DIR"
    if ! git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
        echo -e "${RED}✗${NC} Failed to clone repository."
        echo -e "${CYAN}→${NC} Make sure git is installed and you have network access."
        echo -e "${CYAN}→${NC} Repo: $REPO_URL"
        exit 1
    fi
fi

cd "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Source code ready"

# ============================================================================
# Step 3: Create virtual environment and install
# ============================================================================

echo -e "${CYAN}→${NC} Setting up Python ${PYTHON_VERSION} environment..."

if [ -d "$INSTALL_DIR/venv" ]; then
    rm -rf "$INSTALL_DIR/venv"
fi

$UV_CMD venv "$INSTALL_DIR/venv" --python "$PYTHON_VERSION"
echo -e "${GREEN}✓${NC} Virtual environment created"

echo -e "${CYAN}→${NC} Installing dependencies (this may take a minute)..."
"$INSTALL_DIR/venv/bin/pip" install -e "$INSTALL_DIR" 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Elitza Agent installed"
else
    echo -e "${RED}✗${NC} Installation failed. Check the output above."
    exit 1
fi

# ============================================================================
# Step 4: Add to PATH
# ============================================================================

echo -e "${CYAN}→${NC} Setting up elitza command..."

mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/venv/bin/elitza" "$HOME/.local/bin/elitza"
echo -e "${GREEN}✓${NC} elitza → ~/.local/bin/elitza"

# Add ~/.local/bin to PATH if needed
SHELL_CONFIG=""
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    SHELL_CONFIG="$HOME/.bashrc"
    [ ! -f "$SHELL_CONFIG" ] && SHELL_CONFIG="$HOME/.bash_profile"
else
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_CONFIG="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_CONFIG="$HOME/.bashrc"
    fi
fi

if [ -n "$SHELL_CONFIG" ]; then
    touch "$SHELL_CONFIG" 2>/dev/null || true
    if ! echo "$PATH" | tr ':' '\n' | grep -q "^$HOME/.local/bin$"; then
        if ! grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
            echo "" >> "$SHELL_CONFIG"
            echo "# Elitza Agent — ensure ~/.local/bin is on PATH" >> "$SHELL_CONFIG"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
            echo -e "${GREEN}✓${NC} Added ~/.local/bin to PATH in $SHELL_CONFIG"
        else
            echo -e "${GREEN}✓${NC} ~/.local/bin already in $SHELL_CONFIG"
        fi
    else
        echo -e "${GREEN}✓${NC} ~/.local/bin already on PATH"
    fi
fi

# ============================================================================
# Step 5: Create .env template
# ============================================================================

if [ ! -f "$ELITZA_HOME/.env" ]; then
    mkdir -p "$ELITZA_HOME"
    cat > "$ELITZA_HOME/.env" << 'ENVEOF'
# Elitza Agent Environment Variables
# Get your API key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=
ENVEOF
    echo -e "${GREEN}✓${NC} Created $ELITZA_HOME/.env (template)"
fi

# ============================================================================
# Done
# ============================================================================

echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${NC}"
echo ""
echo "Next steps:"
echo ""

if [ -n "$SHELL_CONFIG" ]; then
    echo "  1. Reload your shell:"
    echo -e "     ${CYAN}source $SHELL_CONFIG${NC}"
    echo ""
fi

echo "  2. Configure your API key:"
echo -e "     ${CYAN}elitza setup${NC}"
echo ""
echo "  3. Start using Elitza:"
echo -e "     ${CYAN}elitza${NC}"
echo ""
echo "Other commands:"
echo "  elitza --list-tools     # Show available tools"
echo "  elitza -m \"hello\"        # Single message mode"
echo "  elitza --help           # Full help"
echo ""

# Run setup wizard
if [ "$RUN_SETUP" = true ]; then
    if [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${YELLOW}⚠${NC} Non-interactive mode detected. Run 'elitza setup' manually to configure."
    else
        read -p "Run setup wizard now? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            echo ""
            "$INSTALL_DIR/venv/bin/elitza" setup
        fi
    fi
fi
