#!/usr/bin/env bash
# ==============================================================================
# CodeSentinel AI - Quick Launcher
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "================================================================="
echo "  Starting CodeSentinel AI..."
echo "  Seminar-Powered Bug Detection & Code Optimizer"
echo "================================================================="

# Set up virtual environment if not present
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    python3 -m venv .venv
    echo "Installing required dependencies from requirements.txt..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    
    # Apply opentelemetry compatibility alias for semgrep
    .venv/bin/python -c "
path = '.venv/lib/python3.9/site-packages/opentelemetry/sdk/_logs/__init__.py'
try:
    with open(path, 'r') as f:
        content = f.read()
    if 'LogData = ReadableLogRecord' not in content:
        with open(path, 'a') as f:
            f.write('\n# Compatibility alias for semgrep\nLogData = ReadableLogRecord\n')
except Exception:
    pass
"
fi

echo ""
echo "🚀 CodeSentinel AI Web Dashboard launching at:"
echo "👉 http://127.0.0.1:8000"
echo ""
echo "Press Ctrl+C to stop the server."
echo "================================================================="

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
