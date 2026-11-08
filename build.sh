#!/usr/bin/env bash
# Build script for Render deployment
set -e

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Creating data directories..."
mkdir -p data/uploads data/projects data/chroma_db

echo "Build complete!"
