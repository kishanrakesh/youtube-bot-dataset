#!/bin/bash
# Compare packages in env.old vs env

echo "=================================================="
echo "Comparing Virtual Environments"
echo "=================================================="
echo ""

# Check if both environments exist
if [ ! -d "env.old" ]; then
    echo "❌ env.old/ does not exist"
    exit 1
fi

if [ ! -d "env" ]; then
    echo "❌ env/ does not exist"
    exit 1
fi

echo "📦 Extracting package lists..."
echo ""

# Get packages from env.old
echo "Getting packages from env.old..."
env.old/bin/python -m pip list --format=freeze > /tmp/env_old_packages.txt 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Failed to get packages from env.old"
    exit 1
fi

# Get packages from env
echo "Getting packages from env..."
env/bin/python -m pip list --format=freeze > /tmp/env_packages.txt 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Failed to get packages from env"
    exit 1
fi

echo ""
echo "=================================================="
echo "PACKAGE COMPARISON"
echo "=================================================="
echo ""

# Count packages
old_count=$(wc -l < /tmp/env_old_packages.txt)
new_count=$(wc -l < /tmp/env_packages.txt)

echo "📊 Package counts:"
echo "   env.old: $old_count packages"
echo "   env:     $new_count packages"
echo ""

# Find packages only in env.old
echo "=================================================="
echo "Packages ONLY in env.old (not in env):"
echo "=================================================="
comm -23 <(sort /tmp/env_old_packages.txt) <(sort /tmp/env_packages.txt) > /tmp/only_in_old.txt
if [ -s /tmp/only_in_old.txt ]; then
    cat /tmp/only_in_old.txt
    echo ""
    echo "Total: $(wc -l < /tmp/only_in_old.txt) packages"
else
    echo "None - all packages from env.old are in env"
fi

echo ""
echo "=================================================="
echo "Packages ONLY in env (not in env.old):"
echo "=================================================="
comm -13 <(sort /tmp/env_old_packages.txt) <(sort /tmp/env_packages.txt) > /tmp/only_in_new.txt
if [ -s /tmp/only_in_new.txt ]; then
    cat /tmp/only_in_new.txt
    echo ""
    echo "Total: $(wc -l < /tmp/only_in_new.txt) packages"
else
    echo "None - all packages from env are in env.old"
fi

echo ""
echo "=================================================="
echo "Version differences (same package, different version):"
echo "=================================================="
# Extract package names and compare versions
while IFS='==' read -r pkg_old ver_old; do
    if grep -q "^${pkg_old}==" /tmp/env_packages.txt; then
        ver_new=$(grep "^${pkg_old}==" /tmp/env_packages.txt | cut -d'=' -f3)
        if [ "$ver_old" != "$ver_new" ]; then
            echo "  $pkg_old: $ver_old (old) -> $ver_new (new)"
        fi
    fi
done < /tmp/env_old_packages.txt

echo ""
echo "=================================================="
echo "RECOMMENDATION"
echo "=================================================="
if [ ! -s /tmp/only_in_old.txt ]; then
    echo "✅ env.old can be SAFELY DELETED"
    echo "   All packages from env.old are present in env"
    echo ""
    echo "💾 Space to be freed: $(du -sh env.old | cut -f1)"
    echo ""
    echo "To delete, run: rm -rf env.old"
else
    echo "⚠️  WARNING: env.old has packages not in env"
    echo "   Review the list above before deleting"
fi
echo "=================================================="

# Cleanup temp files
rm -f /tmp/env_old_packages.txt /tmp/env_packages.txt /tmp/only_in_old.txt /tmp/only_in_new.txt
