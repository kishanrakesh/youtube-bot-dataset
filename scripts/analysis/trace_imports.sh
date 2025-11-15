#!/bin/bash
# Manually trace imports from Makefile entry points

echo "=== Tracing imports for Makefile entry points ==="
echo ""

for file in \
    app/pipeline/trending/fetch.py \
    app/pipeline/trending/load.py \
    app/pipeline/comments/fetch.py \
    app/pipeline/comments/register.py \
    app/pipeline/screenshots/capture.py \
    app/pipeline/screenshots/review.py
do
    echo "File: $file"
    grep -E "^from app\.|^import app\." "$file" 2>/dev/null | sed 's/from /  → /' | sed 's/ import.*//' || echo "  (no app imports)"
    echo ""
done
