#!/bin/bash
# Quick script to launch the web-based image viewer

source env/bin/activate
python scripts/review_images_web.py "$@"
