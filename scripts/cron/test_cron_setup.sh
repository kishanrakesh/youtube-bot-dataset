#!/usr/bin/env bash
# Test script to verify cron setup will work

set -e
cd /root/youtube-bot-dataset

echo "🧪 TESTING CRON SETUP"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Test 1: Script exists and is executable
echo "1️⃣  Checking if run_nightly.sh exists and is executable..."
if [ -x scripts/run_nightly.sh ]; then
    echo "    ✅ Script found and executable"
else
    echo "    ❌ Script not found or not executable"
    exit 1
fi
echo ""

# Test 2: Script syntax is valid
echo "2️⃣  Validating bash syntax..."
if bash -n scripts/run_nightly.sh; then
    echo "    ✅ Script syntax is valid"
else
    echo "    ❌ Script has syntax errors"
    exit 1
fi
echo ""

# Test 3: Virtual environment exists
echo "3️⃣  Checking virtual environment..."
if [ -f env/bin/activate ]; then
    echo "    ✅ Virtual environment found"
    source env/bin/activate
    echo "    Python: $(python --version)"
else
    echo "    ❌ Virtual environment not found"
    exit 1
fi
echo ""

# Test 4: Makefile exists and has required targets
echo "4️⃣  Checking Makefile..."
if [ -f Makefile ]; then
    echo "    ✅ Makefile found"
    if make -n all-categories > /dev/null 2>&1; then
        echo "    ✅ Target 'all-categories' exists"
    else
        echo "    ❌ Target 'all-categories' not found or has errors"
        exit 1
    fi
else
    echo "    ❌ Makefile not found"
    exit 1
fi
echo ""

# Test 5: Crontab is installed
echo "5️⃣  Verifying crontab..."
if crontab -l | grep -q "run_nightly.sh"; then
    echo "    ✅ Crontab entry found"
    crontab -l | grep "run_nightly.sh"
else
    echo "    ❌ Crontab entry not found"
    exit 1
fi
echo ""

# Test 6: Logs directory exists
echo "6️⃣  Checking logs directory..."
if [ -d logs ]; then
    echo "    ✅ Logs directory exists"
else
    echo "    ⚠️  Creating logs directory..."
    mkdir -p logs
    echo "    ✅ Logs directory created"
fi
echo ""

# Test 7: flock command available
echo "7️⃣  Checking for flock command..."
if command -v flock &> /dev/null; then
    echo "    ✅ flock is available"
else
    echo "    ❌ flock not found (install with: apt-get install util-linux)"
    exit 1
fi
echo ""

# Test 8: Cron service running
echo "8️⃣  Checking cron service..."
if systemctl is-active --quiet cron 2>/dev/null || service cron status &>/dev/null; then
    echo "    ✅ Cron service is running"
else
    echo "    ❌ Cron service is not running"
    exit 1
fi
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "✅ ALL CHECKS PASSED!"
echo ""
echo "📝 Next Steps:"
echo "   • To test the actual script manually:"
echo "     bash scripts/run_nightly.sh"
echo ""
echo "   • To simulate the cron command:"
echo "     flock -n /tmp/ytbot.lock bash -lc 'cd /root/youtube-bot-dataset && scripts/run_nightly.sh'"
echo ""
echo "   • To monitor cron logs when it runs:"
echo "     tail -f logs/nightly_pipeline.log"
echo ""
echo "   • Your cron will run at: midnight CT (America/Chicago)"
echo "     Next run: $(TZ=America/Chicago date -d 'tomorrow 00:00' '+%Y-%m-%d %H:%M:%S %Z')"
echo ""
