#!/usr/bin/env bash
set -euo pipefail

cd /root/youtube-bot-dataset

# Activate venv
source env/bin/activate

# (If you use ADC) point to your service account JSON:
# export GOOGLE_APPLICATION_CREDENTIALS="/root/youtube-bot-dataset/adc.json"

# Optional: ensure Chromium path for Playwright is on PATH (usually not needed)
# export PLAYWRIGHT_BROWSERS_PATH=$PWD/ms-playwright

# Run the full workflow
make all-categories
