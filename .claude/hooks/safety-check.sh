#!/bin/bash
# WUTT Safety Hook — PreToolUse
# Blocks dangerous commands before execution

COMMAND="$1"

# Block rm -rf
if echo "$COMMAND" | grep -q "rm -rf"; then
    echo "🚫 BLOCKED: rm -rf is not allowed in WUTT project"
    exit 2
fi

# Block .env modifications
if echo "$COMMAND" | grep -q "\.env" && echo "$COMMAND" | grep -qE "write|edit|delete|rm"; then
    echo "🚫 BLOCKED: .env file cannot be modified by Claude"
    exit 2
fi

# Block direct main branch push
if echo "$COMMAND" | grep -q "git push origin main"; then
    echo "⚠️  WARNING: Direct push to main blocked. Use feature branch."
    exit 2
fi

# Block SQL DROP commands
if echo "$COMMAND" | grep -qi "DROP TABLE\|DROP DATABASE"; then
    echo "🚫 BLOCKED: Destructive SQL commands not allowed"
    exit 2
fi

echo "✅ Safety check passed"
exit 0
