#!/bin/bash
set -euo pipefail

# Full project code review script for Veloro.
# Runs linters and quality checks across the entire codebase.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

echo "============================================"
echo "  Veloro Code Review - Full Project Scan"
echo "============================================"
echo ""

# --- Python Backend ---
echo "--- Backend (Python) ---"
echo ""

# 1. Ruff linting
if command -v ruff &>/dev/null; then
    echo "[1/4] Running ruff (lint)..."
    if ! ruff check "$PROJECT_DIR/backend/" 2>&1; then
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
else
    echo "[1/4] SKIPPED: ruff not installed (pip install ruff)"
    echo ""
fi

# 2. Check for large files
echo "[2/4] Checking for oversized files (>300 lines)..."
FOUND_LARGE=0
while IFS= read -r -d '' file; do
    lines=$(wc -l < "$file")
    if [ "$lines" -gt 300 ]; then
        echo "  WARNING: $file ($lines lines) -- consider splitting"
        FOUND_LARGE=1
    fi
done < <(find "$PROJECT_DIR/backend" -name "*.py" -print0)
if [ "$FOUND_LARGE" -eq 0 ]; then
    echo "  All files under 300 lines"
fi
echo ""

# 3. Check for bare except
echo "[3/4] Checking for bare except patterns..."
BARE_EXCEPT=$(grep -rn "except.*:" "$PROJECT_DIR/backend/" --include="*.py" | grep -E "except\s*(Exception)?\s*:" | grep -v "except.*Error" | grep -v "# noqa" | head -20) || true
if [ -n "$BARE_EXCEPT" ]; then
    echo "$BARE_EXCEPT"
else
    echo "  None found"
fi
echo ""

# 4. Check for missing type hints on function defs
echo "[4/4] Checking for functions missing return type hints..."
MISSING_HINTS=$(grep -rn "def " "$PROJECT_DIR/backend/" --include="*.py" | grep -v "->.*:" | grep -v "__" | grep -v "test_" | head -20) || true
if [ -n "$MISSING_HINTS" ]; then
    echo "$MISSING_HINTS"
else
    echo "  None found"
fi
echo ""

# --- React Frontend ---
echo "--- Frontend (React) ---"
echo ""

# 5. ESLint
echo "[5/7] Running ESLint..."
if [ -f "$PROJECT_DIR/frontend/node_modules/.bin/eslint" ]; then
    (cd "$PROJECT_DIR/frontend" && npx eslint . 2>&1) || ERRORS=$((ERRORS + 1))
else
    echo "  SKIPPED: eslint not installed (cd frontend && npm install)"
fi
echo ""

# 6. Check for console.log
echo "[6/7] Checking for console.log statements..."
CONSOLE_LOGS=$(grep -rn "console\.log" "$PROJECT_DIR/frontend/src/" --include="*.jsx" --include="*.js" | grep -v "// debug" | head -20) || true
if [ -n "$CONSOLE_LOGS" ]; then
    echo "$CONSOLE_LOGS"
else
    echo "  None found"
fi
echo ""

# 7. Check for large components
echo "[7/7] Checking for oversized components (>300 lines)..."
FOUND_LARGE_FE=0
while IFS= read -r -d '' file; do
    lines=$(wc -l < "$file")
    if [ "$lines" -gt 300 ]; then
        echo "  WARNING: $file ($lines lines) -- consider splitting"
        FOUND_LARGE_FE=1
    fi
done < <(find "$PROJECT_DIR/frontend/src" \( -name "*.jsx" -o -name "*.js" \) -print0)
if [ "$FOUND_LARGE_FE" -eq 0 ]; then
    echo "  All files under 300 lines"
fi
echo ""

# --- Summary ---
echo "============================================"
if [ $ERRORS -gt 0 ]; then
    echo "  Review complete: $ERRORS check(s) had issues"
else
    echo "  Review complete: All checks passed"
fi
echo "============================================"

exit $ERRORS
