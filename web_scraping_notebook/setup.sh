#!/bin/bash
# Quick setup script for the web scraping notebook

echo "Setting up Epidemiology Web Scraper..."
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Create virtual environment (optional but recommended)
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To start the notebook:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Launch Jupyter: jupyter notebook epidemiology_web_scraper.ipynb"
echo ""
echo "Or run directly:"
echo "  jupyter notebook epidemiology_web_scraper.ipynb"
