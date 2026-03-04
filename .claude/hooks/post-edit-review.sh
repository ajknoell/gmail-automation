#!/bin/bash
set -euo pipefail

# PostToolUse hook: runs lightweight lint checks after every file edit.
# Receives JSON on stdin with tool_input containing the edited file path.
# Always exits 0 -- output flows back to Claude as context for self-correction.

INPUT=$(cat)

# Extract the file path from the tool input JSON
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    ti = data.get('tool_input', {})
    print(ti.get('file_path', ti.get('filePath', '')))
except Exception:
    print('')
" 2>/dev/null)

# Exit silently if we couldn't determine the file
if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Determine file type and run the appropriate linter
case "$FILE_PATH" in
    *.py)
        # Run ruff if available (fast Python linter)
        if command -v ruff &>/dev/null; then
            OUTPUT=$(ruff check --select=E,W,F,S,B "$FILE_PATH" 2>&1) || true
            if [ -n "$OUTPUT" ]; then
                echo "=== Python Quality Check ==="
                echo "$OUTPUT"
                echo "==========================="
            fi
        fi
        ;;
    *.js|*.jsx)
        # Run eslint if available and we're in the frontend directory
        if echo "$FILE_PATH" | grep -q "frontend/"; then
            FRONTEND_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo '.')}/frontend"
            if [ -f "$FRONTEND_DIR/node_modules/.bin/eslint" ]; then
                OUTPUT=$(cd "$FRONTEND_DIR" && npx eslint "$FILE_PATH" 2>&1) || true
                if [ -n "$OUTPUT" ] && ! echo "$OUTPUT" | grep -q "0 problems"; then
                    echo "=== JavaScript Quality Check ==="
                    echo "$OUTPUT"
                    echo "================================"
                fi
            fi
        fi
        ;;
esac

exit 0
