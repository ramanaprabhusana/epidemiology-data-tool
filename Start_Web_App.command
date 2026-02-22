#!/bin/bash
cd "$(dirname "$0")"

# If the tool is already running, just open the browser and exit (avoids extra terminal windows and duplicate servers)
if [ -f .webapp_port ]; then
  p=$(cat .webapp_port 2>/dev/null)
  if [ -n "$p" ] && curl -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:$p/" 2>/dev/null; then
    echo ""
    echo "Epidemiology Data Tool is already running at http://127.0.0.1:$p"
    echo "Opening in browser. You can close this window — use the original window where the tool was first started."
    echo ""
    open "http://127.0.0.1:$p/"
    read -p "Press Enter to close this window."
    exit 0
  fi
fi

# Use venv Python directly (works when double-clicked from Finder)
PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "No .venv found or Python missing. Run in Terminal:"
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    read -p "Press Enter to close."
    exit 1
fi

echo ""
echo "Epidemiology Data Tool is starting."
echo "Browser will open when ready. Keep this window open while using the tool."
echo ""
"$PYTHON" app_web.py

read -p "Press Enter to close."
