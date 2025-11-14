#!/bin/bash
# Quick script to launch the web-based image annotator

source env/bin/activate
python scripts/annotate_images_web.py "$@"
