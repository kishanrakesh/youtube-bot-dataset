# Makefile Testing Guide

**Quick Reference for Testing Each Make Command with Minimal Data**

Last Updated: November 14, 2025

---

## ✅ Individual Command Tests (Minimal Data)

### 1. `fetch-trending` - Fetch trending videos
```bash
make fetch-trending TRENDING_PAGES=1 CATEGORY=0
```
**What it does:** Fetches 50 trending videos (1 page) and stores to GCS  
**Data volume:** 50 videos  
**Time:** ~5 seconds  
**Output:** `youtube-bot-dataset/video_metadata/trending/raw/{date}/US_0_page_1.json`

---

### 2. `load-trending` - Load videos to BigQuery
```bash
make load-trending TRENDING_PAGES=1 CATEGORY=0
```
**What it does:** Loads fetched trending videos into BigQuery  
**Data volume:** 50 videos  
**Time:** ~3 seconds  
**Prerequisite:** Must run `fetch-trending` first  
**Output:** Videos loaded to BigQuery table

---

### 3. `fetch-comments` - Fetch comments for videos
```bash
make fetch-comments TRENDING_PAGES=1 CATEGORY=0 COMMENT_PAGES=1
```
**What it does:** Fetches comments for all trending videos  
**Data volume:** ~50 videos × 100 comments = 5,000 comments  
**Time:** ~2-3 minutes  
**Prerequisite:** Must run `fetch-trending` first  
**Output:** `youtube-bot-dataset/video_comments/raw/{video_id}.json`  
**Note:** ⚠️ Processes ALL videos from trending page (no video limit parameter)

---

### 4. `register-commenters` - Register commenter channels
```bash
make register-commenters REVIEW_LIMIT=1
```
**What it does:** Processes 1 comment file, extracts and registers commenter channels to Firestore  
**Data volume:** 1 comment file (~100 comments)  
**Time:** ~10 seconds  
**Prerequisite:** Must run `fetch-comments` first  
**Output:** New channels registered in Firestore  
**Expected:** Registers ~2-20 unique commenter channels per file

---

### 5. `capture-screenshots` - Capture channel screenshots
```bash
make capture-screenshots SCREENSHOT_LIMIT=1
```
**What it does:** Captures screenshots of 1 channel using Playwright  
**Data volume:** 1 channel  
**Time:** ~15-30 seconds per channel  
**Prerequisite:** 
- Must run `register-commenters` first
- Requires Playwright: `playwright install chromium`
**Output:** Screenshot uploaded to GCS at `yt-bot-screens/channel_screenshots/raw/`  
**Note:** Some channels may timeout (expected behavior)

---

### 6. `review` - Launch manual review UI
```bash
make review REVIEW_LIMIT=1
```
**What it does:** Opens FastAPI UI for manually labeling screenshots  
**Data volume:** 1 screenshot  
**Time:** Manual (interactive)  
**Prerequisite:** Must have unlabeled screenshots (from `capture-screenshots`)  
**Output:** Interactive web UI at `http://localhost:8000`  
**Note:** If no unlabeled screenshots exist, shows "No docs to review"

---

## 🔄 Workflow Tests (Combined Commands)

### Minimal End-to-End: Trending → Comments
```bash
make trending-to-comments TRENDING_PAGES=1 CATEGORY=0 COMMENT_PAGES=1
```
**Runs:** `fetch-trending` + `fetch-comments`  
**Time:** ~2-3 minutes  
**Data:** 50 videos + ~5,000 comments

---

### Minimal Annotation Workflow
```bash
make register-capture REVIEW_LIMIT=1 SCREENSHOT_LIMIT=1
```
**Runs:** `register-commenters` + `capture-screenshots`  
**Time:** ~30-60 seconds  
**Data:** 1 comment file + 1 screenshot

---

## 📊 Default Values (from Makefile)

| Variable | Default | Minimal for Testing |
|----------|---------|---------------------|
| `TRENDING_REGION` | US | US |
| `CATEGORY` | 27 | 0 (general) |
| `DATE` | Today | Today |
| `TRENDING_PAGES` | 50 | 1 |
| `COMMENT_PAGES` | 20 | 1 |
| `SCREENSHOT_LIMIT` | 200 | 1 |
| `REVIEW_LIMIT` | 100 | 1 |

---

## 🎯 Recommended Test Sequence

For a complete minimal test of the entire pipeline:

```bash
# 1. Fetch minimal trending data
make fetch-trending TRENDING_PAGES=1 CATEGORY=0

# 2. Load to BigQuery
make load-trending TRENDING_PAGES=1 CATEGORY=0

# 3. Fetch minimal comments (⚠️ takes 2-3 min for 50 videos)
make fetch-comments TRENDING_PAGES=1 CATEGORY=0 COMMENT_PAGES=1

# 4. Register commenters from 1 file
make register-commenters REVIEW_LIMIT=1

# 5. Capture 1 screenshot
make capture-screenshots SCREENSHOT_LIMIT=1

# 6. Review (if unlabeled screenshots exist)
make review REVIEW_LIMIT=1
```

**Total time:** ~3-5 minutes  
**Total data:** 50 videos, ~5,000 comments, ~2-20 channels, 1 screenshot

---

## ⚠️ Important Notes

1. **Category 27 Error:** Default category 27 may not exist for all regions. Use `CATEGORY=0` for general trending instead.

2. **Playwright Requirement:** Commands 4-6 require Playwright browsers:
   ```bash
   playwright install chromium
   ```

3. **No Video Limit:** `fetch-comments` processes ALL videos from the trending page. Minimal = 1 trending page (50 videos).

4. **Model Warnings:** You may see warnings like "No model found at xgb_bot_model.pkl" - this is expected if you haven't trained a bot detection model yet.

5. **Screenshot Timeouts:** Some channels may timeout during screenshot capture - this is normal behavior.

6. **Review UI:** The `review` command launches a web server. Press Ctrl+C to stop it.

---

## 🔧 Troubleshooting

**Error: "Requested entity was not found" (Category 27)**
- Solution: Use `CATEGORY=0` instead

**Error: "Executable doesn't exist" (Playwright)**
- Solution: Run `playwright install chromium`

**Warning: "No model found at xgb_bot_model.pkl"**
- Not an error - just means bot probability scoring is skipped
- Train a model if you want scoring enabled

**"No docs to review"**
- This is correct if no unlabeled screenshots exist
- Run `capture-screenshots` first, then `review`

---

## 📈 Scaling Up

Once you've verified everything works with minimal data, scale up by adjusting the parameters:

```bash
# Production-like settings
make all-categories TRENDING_PAGES=50 COMMENT_PAGES=20 SCREENSHOT_LIMIT=200
```

This will process all 11 video categories with full pagination.
