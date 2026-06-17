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

# Resolve absolute path if relative
if [[ "$FILE_PATH" != /* ]]; then
    FILE_PATH="/home/usertainsinmoe/wutt/$FILE_PATH"
fi

if [ ! -f "$FILE_PATH" ]; then
    echo "⚠️  Format check skipped — file not found: $FILE_PATH"
    exit 0
fi

WARNINGS=0

# Check for trailing whitespace
if grep -nE '[[:space:]]+$' "$FILE_PATH" 2>/dev/null | head -5; then
    echo "⚠️  Trailing whitespace found in: $FILE_PATH"
    WARNINGS=$((WARNINGS + 1))
fi

# Check for tabs in Python files
if [[ "$FILE_PATH" == *.py ]]; then
    if grep -nP '^\t' "$FILE_PATH" 2>/dev/null | head -3; then
        echo "⚠️  Tab indentation found in Python file: $FILE_PATH"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Check for missing newline at EOF
if [ -s "$FILE_PATH" ] && [ "$(tail -c 1 "$FILE_PATH" | wc -l)" -eq 0 ]; then
    echo "⚠️  Missing newline at EOF: $FILE_PATH"
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$WARNINGS" -gt 0 ]; then
    echo "⚠️  Format check: $WARNINGS warning(s) in $FILE_PATH"
    exit 0  # Warnings don't block — just notify
fi

echo "✅ Format check passed: $FILE_PATH"
exit 0
