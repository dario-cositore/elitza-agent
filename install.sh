#!/bin/bash
# ============================================================================
# Elitza Agent Install Script
# ============================================================================
# One-liner install:
#   curl -fsSL https://elitza.life/install.sh | bash
#
# This script:
# 1. Installs uv (Python package manager) if needed
# 2. Creates a virtual environment and installs Elitza Agent from GitHub
# 3. Adds the elitza command to ~/.local/bin
# 4. Ensures ~/.local/bin is on PATH
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

REPO_URL="https://github.com/dario-cositore/elitza-agent.git"
INSTALL_DIR="$HOME/.elitza/agent"

echo ""
echo -e "${CYAN}Elitza Agent Installer${NC}"
echo ""

# ============================================================================
# Install / locate uv
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
            echo -e "${RED}✗${NC} uv installer reported success but binary not found. Add ~/.local/bin to PATH and retry."
            sed 's/^/    /' "$_uv_log" >&2
            rm -f "$_uv_log"
            exit 1
        fi
    else
        echo -e "${RED}✗${NC} Failed to install uv."
        echo -e "${CYAN}→${NC} Installer output:"
        sed 's/^/    /' "$_uv_log" >&2
        echo -e "${CYAN}→${NC} Install manually: https://docs.astral.sh/uv/"
        rm -f "$_uv_log" "$_uv_installer"
        exit 1
    fi
fi

# ============================================================================
# Clone or update the repo
# ============================================================================

echo -e "${CYAN}→${NC} Installing Elitza Agent..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${CYAN}→${NC} Existing install found, updating..."
    cd "$INSTALL_DIR"
    git pull origin main 2>&1 | tail -3
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | tail -3
fi

# ============================================================================
# Create venv and install dependencies
# ============================================================================

echo -e "${CYAN}→${NC} Setting up Python environment..."

cd "$INSTALL_DIR"

# Remove old venv for clean install
if [ -d ".venv" ]; then
    rm -rf .venv
fi

$UV_CMD venv .venv --python 3.11
echo -e "${GREEN}✓${NC} Virtual environment created"

echo -e "${CYAN}→${NC} Installing dependencies..."
$UV_CMD pip install -e . 2>&1 | tail -3
echo -e "${GREEN}✓${NC} Dependencies installed"

# ============================================================================
# Create CLI wrapper at ~/.local/bin/elitza
# ============================================================================

echo -e "${CYAN}→${NC} Setting up elitza command..."

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/elitza" << 'WRAPPER'
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$HOME/.elitza/agent/.venv/bin/elitza" "$@"
WRAPPER

chmod +x "$HOME/.local/bin/elitza"
echo -e "${GREEN}✓${NC} elitza command installed → ~/.local/bin/elitza"

# ============================================================================
# Ensure ~/.local/bin is on PATH
# ============================================================================

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
    elif [ -f "$HOME/.bash_profile" ]; then
        SHELL_CONFIG="$HOME/.bash_profile"
    fi
fi

if [ -n "$SHELL_CONFIG" ]; then
    touch "$SHELL_CONFIG" 2>/dev/null || true
    if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
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
# Done
# ============================================================================

echo ""
echo -e "${GREEN}✓ Install complete!${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Reload your shell (if PATH was updated):"
echo "     source $SHELL_CONFIG"
echo ""
echo "  2. Run the setup wizard to configure your OpenRouter API key:"
echo "     elitza setup"
echo ""
echo "  3. Start chatting:"
echo "     elitza"
echo ""
echo "Other commands:"
echo "  elitza -m \"hello\"     # Single message"
echo "  elitza --help         # Full help"
echo ""

# Ask if they want to run setup wizard now
read -p "Run the setup wizard now? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    echo ""
    "$HOME/.local/bin/elitza" setup
fi
