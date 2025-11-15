# Cron Testing & Monitoring Guide

## ✅ Setup Verified

Your cron setup has been tested and verified. All checks passed:
- ✅ Script exists and is executable
- ✅ Bash syntax is valid
- ✅ Virtual environment configured
- ✅ Makefile targets exist
- ✅ Crontab installed correctly
- ✅ Logs directory created
- ✅ `flock` command available
- ✅ Cron service running

## 📅 Schedule

**When it runs:** Daily at midnight CT (America/Chicago)  
**What it runs:** `make all-categories` via `/root/youtube-bot-dataset/scripts/run_nightly.sh`  
**Log file:** `/root/youtube-bot-dataset/logs/nightly_pipeline.log`

## 🧪 Testing Options

### Option 1: Quick Verification Test (Recommended, ~5 min)
Test a single category with reduced pagination:
```bash
cd /root/youtube-bot-dataset
source env/bin/activate
make trending-to-comments CATEGORY=10 TRENDING_PAGES=2 COMMENT_PAGES=2
```

### Option 2: Dry Run (Shows commands without executing)
See exactly what will run without actually running it:
```bash
cd /root/youtube-bot-dataset
make -n all-categories
```

### Option 3: Full Nightly Script Test (Hours!)
Run the complete nightly pipeline manually:
```bash
cd /root/youtube-bot-dataset
bash scripts/run_nightly.sh
```

### Option 4: Simulate Cron Execution
Run exactly as cron would, with output to test log:
```bash
flock -n /tmp/ytbot.lock bash -lc '/root/youtube-bot-dataset/scripts/run_nightly.sh' >> logs/manual_test.log 2>&1 &
tail -f logs/manual_test.log
```

## 📊 Monitoring

### View Live Logs
```bash
tail -f /root/youtube-bot-dataset/logs/nightly_pipeline.log
```

### Check if Cron Ran
```bash
# Check cron execution history
grep CRON /var/log/syslog | grep run_nightly

# Check if lock file exists (indicates currently running)
ls -lh /tmp/ytbot.lock
```

### View Last 100 Lines of Log
```bash
tail -100 /root/youtube-bot-dataset/logs/nightly_pipeline.log
```

## 🔧 Troubleshooting

### Check Crontab
```bash
crontab -l
```

### Edit Crontab
```bash
crontab -e
```

### Check Cron Service
```bash
systemctl status cron
# or
service cron status
```

### Manually Trigger Cron
If you want to force an immediate run (bypass schedule):
```bash
cd /root/youtube-bot-dataset
flock -n /tmp/ytbot.lock bash -lc "$(pwd)/scripts/run_nightly.sh" >> logs/manual_run.log 2>&1 &
```

### Check for Running Processes
```bash
# See if nightly script is currently running
ps aux | grep run_nightly

# See if any Python pipeline processes are running
ps aux | grep "app.pipeline"
```

## 📈 What Runs Each Night

1. **Fetch Trending Videos** for 11 categories (1, 2, 10, 15, 17, 20, 22, 23, 24, 25, 26)
   - Up to 50 pages per category
   
2. **Fetch Comments** from trending videos
   - Up to 20 comment pages per video
   
3. **Register & Screenshot Loop** (10 iterations with 60s delays)
   - Register up to 100 new commenter channels
   - Capture up to 200 screenshots

## ⚙️ Customization

To modify the cron schedule or parameters:

1. Edit the crontab:
   ```bash
   crontab -e
   ```

2. Or modify Makefile defaults:
   ```bash
   vim /root/youtube-bot-dataset/Makefile
   ```
   
3. Or modify the nightly script:
   ```bash
   vim /root/youtube-bot-dataset/scripts/run_nightly.sh
   ```

## 🎯 Quick Test Command

To verify everything works right now:
```bash
bash /root/youtube-bot-dataset/test_cron_setup.sh
```

This will run all verification checks and tell you if the setup is valid.
