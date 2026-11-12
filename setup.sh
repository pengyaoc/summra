#!/bin/bash

# Summra setup: one venv for the shared platform, Plainly and Distill

echo "================================"
echo "  Summra Setup"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r plainly/requirements.txt -r distill/requirements.txt
pip install -e .

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your GEMINI_API_KEY"
    echo "   Get your API key from: https://makersuite.google.com/app/apikey"
else
    echo ""
    echo "✓ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating data directories..."
mkdir -p data/books data/summaries plainly/frontend/static/audio

echo ""
echo "================================"
echo "  Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "  Plainly (classics, :5001)"
echo "    1. Edit .env and add your GEMINI_API_KEY (needed only to ingest books)"
echo "    2. Restore data/database.db, or ingest a book (see plainly/README.md)"
echo "    3. python plainly/app.py  ->  http://localhost:5001"
echo "  Distill (private summaries, :5003)"
echo "    1. Import a book folder: python -m distill.scripts.push_book <folder>"
echo "    2. python -m distill.app  ->  http://localhost:5003"
echo ""
echo "For more information, see README.md"
echo ""
