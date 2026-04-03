#!/bin/bash
# Build script — installs system dependencies + Python packages
# Works on Render, Railway, and other Linux-based deployment platforms

set -e

echo "Installing system dependencies (ffmpeg for audio processing)..."
apt-get update && apt-get install -y --no-install-recommends ffmpeg

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Build complete."
