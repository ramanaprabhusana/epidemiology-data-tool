#!/bin/bash
# Mac launcher script - double-click to start Jupyter notebook

cd "$(dirname "$0")"

echo "Starting Epidemiology Web Scraper Notebook..."
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found. Installing dependencies globally..."
fi

# Check if dependencies are installed
if ! python3 -c "import jupyter" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Launch Jupyter
echo "Launching Jupyter Notebook..."
echo "The notebook will open in your browser automatically."
echo ""
jupyter notebook epidemiology_web_scraper.ipynb

# Keep terminal open
read -p "Press Enter to close..."
