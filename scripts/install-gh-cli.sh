#!/usr/bin/env bash
# Install GitHub CLI (gh) on Linux
# Usage: ./scripts/install-gh-cli.sh
# Docs: https://cli.github.com/

set -euo pipefail

if command -v gh &>/dev/null; then
    echo "GitHub CLI is already installed: $(gh --version | head -1)"
    exit 0
fi

# Detect the package manager and install accordingly
if command -v apt-get &>/dev/null; then
    echo "Installing GitHub CLI via apt..."
    (type -p wget >/dev/null || sudo apt-get install wget -y)
    sudo mkdir -p -m 755 /etc/apt/keyrings
    out=$(mktemp)
    wget -nv -O "$out" https://cli.github.com/packages/githubcli-archive-keyring.gpg
    cat "$out" | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update
    sudo apt-get install gh -y
elif command -v dnf &>/dev/null; then
    echo "Installing GitHub CLI via dnf..."
    sudo dnf install 'dnf-command(config-manager)' -y
    sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
    sudo dnf install gh -y
elif command -v brew &>/dev/null; then
    echo "Installing GitHub CLI via Homebrew..."
    brew install gh
else
    echo "Error: No supported package manager found (apt, dnf, or brew)."
    echo "Please install manually: https://cli.github.com/"
    exit 1
fi

echo "GitHub CLI installed successfully: $(gh --version | head -1)"
echo ""
echo "Next steps:"
echo "  1. Authenticate with: gh auth login"
echo "  2. Verify with:       gh auth status"
