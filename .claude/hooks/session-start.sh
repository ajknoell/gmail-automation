#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing backend Python dependencies..."
cd "$CLAUDE_PROJECT_DIR/backend"
pip install -r requirements.txt
pip install ruff  # Code review agent dependency

echo "Installing frontend Node.js dependencies..."
cd "$CLAUDE_PROJECT_DIR/frontend"
npm install

echo "Session start hook completed successfully."
