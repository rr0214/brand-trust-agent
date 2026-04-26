#!/bin/bash
# Brand Trust Agent — Quick Start
# Run this from the brand-trust-agent/ directory

set -e

echo ""
echo "🛡️  Brand Trust Agent — Setup & Launch"
echo "========================================"

# Check for .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "   → Edit .env and add your OPENAI_API_KEY before continuing."
    echo "   → ARIZE_SPACE_ID and ARIZE_API_KEY are optional to start."
    echo ""
    echo "Open .env now, add your keys, then re-run this script."
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "✅ Ready. Launching Streamlit..."
echo "   App will open at: http://localhost:8501"
echo ""

streamlit run app.py
