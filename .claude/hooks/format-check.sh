#!/bin/bash
# WUTT Format Check Hook — PostToolUse
# Runs after Write/Edit/MultiEdit to verify code style consistency.
# Returns 0 on success, 1 on warnings, 2 on errors.

TOOL_NAME="$1"
FILE_PATH="$2"

# Only check if a file path was provided
if [ -z "$FILE_PATH" ]; then
    echo "✅ Format check skipped — no file path"
    exit 0
fi

# Only check source files
case "$FILE_PATH" in
    *.py|*.js|*.css|*.html|*.md|*.yaml|*.yml|*.json) ;;
    *) echo "✅ Format check skipped — non-source file"; exit 0 ;;
esac

# Resolve repo root dynamically — works on any machine
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/wutt")

# Resolve absolute path if relative
if [[ "$FILE_PATH" != /* ]]; then
    FILE_PATH="${REPO_ROOT}/${FILE_PATH}"
fi

if [ ! -f "$FILE_PATH" ]; then
    echo "⚠️  Format check skipped — file not found: $FILE_PATH"
    exit 0
fi

WARNINGS=0

# Check for trailing whitespace (spaces/tabs only, not newlines)
TRAILING=$(grep -nE '[[:blank:]]+$' "$FILE_PATH" 2>/dev/null | head -5)
if [ -n "$TRAILING" ]; then
    echo "$TRAILING"
    echo "⚠️  Trailing whitespace found in: $FILE_PATH"
    WARNINGS=$((WARNINGS + 1))
fi

# Check for tabs in Python files
if [[ "$FILE_PATH" == *.py ]]; then
    TABS=$(grep -nE '^\t' "$FILE_PATH" 2>/dev/null | head -3)
    if [ -n "$TABS" ]; then
        echo "$TABS"
        echo "⚠️  Tab indentation found in Python file: $FILE_PATH"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Check for missing newline at EOF (portable across GNU/BSD)
if [ -s "$FILE_PATH" ] && [ -n "$(tail -c 1 "$FILE_PATH")" ]; then
    echo "⚠️  Missing newline at EOF: $FILE_PATH"
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$WARNINGS" -gt 0 ]; then
    echo "⚠️  Format check: $WARNINGS warning(s) in $FILE_PATH"
    exit 0  # Warnings don't block — just notify
fi

echo "✅ Format check passed: $FILE_PATH"
exit 0
