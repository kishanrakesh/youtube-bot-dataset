# Quick Start: Clean Up app/ Directory

## TL;DR - Do This First (5 minutes, ZERO RISK)

```bash
cd /root/youtube-bot-dataset

# Remove duplicate directories (100% safe)
rm -rf app/pipeline/pipeline/
rm -rf app/screenshots/screenshots/

# Remove empty directories (100% safe)
rmdir app/bigquery app/config app/gcs app/parser 2>/dev/null || true

# Verify nothing broke
python -c "from app.utils.clients import get_youtube" && echo "✅ Imports still work"
```

**Impact**: Cleaner structure, no functional changes  
**Risk**: 0%  
**Benefit**: Removes confusion, reduces clutter

---

## Current Problems (Ranked by Severity)

### 🚨 CRITICAL (Fix Now)
1. **Duplicate nested directories**
   - `app/pipeline/pipeline/` - exact copy of parent
   - `app/screenshots/screenshots/` - exact copy of parent
   - **Fix**: Delete them (see above)

### ⚠️ HIGH (Fix This Sprint)
2. **4 Empty directories**
   - `app/bigquery/`, `app/config/`, `app/gcs/`, `app/parser/`
   - **Fix**: Delete them (see above)

3. **Poor organization in `app/analysis/`**
   - 8 files mixed: training, scoring, visualization
   - **Fix**: Create subdirectories (2 hours)

4. **Poor organization in `app/pipeline/`**
   - 13 files mixed: trending, comments, screenshots, domains
   - **Fix**: Create subdirectories by domain (4 hours)

### 💡 NICE-TO-HAVE (Next Quarter)
5. **13 DTO files → Could be 5**
   - `app/models/` has too many tiny files
   - **Fix**: Consolidate related DTOs (3 hours)

6. **7 YouTube API files → Could be 4**
   - `app/youtube_api/` could group by resource
   - **Fix**: Optional consolidation (3 hours)

---

## Recommended Sequence

### This Week (High ROI, Low Risk)
```bash
# 1. Quick wins (5 min)
rm -rf app/pipeline/pipeline/ app/screenshots/screenshots/
rmdir app/bigquery app/config app/gcs app/parser 2>/dev/null

# 2. Organize analysis/ (2 hours)
cd app/analysis
mkdir -p training inference evaluation visualization
mv train_kmeans_pca.py training/
mv ranking_model.py training/train_xgboost.py
mv classifier_utils.py inference/
mv score_channels.py inference/
mv rank_bot_candidates.py evaluation/
mv suggest_thresholds.py evaluation/
mv compare_avatar_metrics.py evaluation/
mv visualize_clusters.py visualization/
# Keep export_script.py at top level

# Add __init__.py files
touch training/__init__.py inference/__init__.py evaluation/__init__.py visualization/__init__.py

# Test
python -c "from app.analysis.inference.classifier_utils import get_pca_kmeans_model"
```

### Next Week (Medium Risk, High Value)
```bash
# 3. Organize pipeline/ (4 hours)
cd app/pipeline
mkdir -p trending comments channels screenshots domains bot_detection

# Move files
mv fetch_trending.py trending/fetch.py
mv load_trending.py trending/load.py
mv fetch_video_comments.py comments/fetch.py
mv register_commenters.py comments/register.py
mv backfill_channels.py channels/backfill.py
mv cleanup_handles.py channels/cleanup.py
mv expand_bot_graph.py channels/scraping.py
mv capture_screenshots.py screenshots/capture.py
mv review_channels.py screenshots/review.py
mv resolve_channel_domains.py domains/resolve.py
mv backfill_probabilities.py bot_detection/backfill.py

# Add __init__.py files
find . -type d -exec touch {}/__init__.py \;

# Update Makefile (see below)
```

**Update Makefile** after pipeline reorganization:
```makefile
# Before:
# python -m app.pipeline.fetch_trending

# After:
# python -m app.pipeline.trending.fetch
```

### Future (Optional, Lower Priority)
- Consolidate DTOs (13 files → 5 files)
- Consolidate YouTube API (7 files → 4 files)
- Move screenshot/labelling into pipeline

---

## Testing After Each Change

```bash
# 1. Test imports
python -c "from app.utils.clients import get_youtube"
python -c "from app.models.ChannelDTO import ChannelDTO"

# 2. Run tests
python -m pytest tests/ -v

# 3. Test a pipeline
make fetch-trending TRENDING_PAGES=1

# 4. Check for broken imports
grep -r "from app.pipeline.fetch_trending" . | grep -v ".pyc"
# Should return nothing (or update those files)
```

---

## Rollback Plan

If anything breaks:
```bash
git status  # See what changed
git checkout app/  # Restore original
# Or restore specific file:
git checkout app/pipeline/fetch_trending.py
```

---

## Expected Benefits

### After Phase 1 (This Week - 2 hours)
- ✅ 6 fewer directories (4 empty + 2 duplicates)
- ✅ Clearer `app/analysis/` structure
- ✅ Easier to find training vs inference code

### After Phase 2 (Next Week - 4 hours)
- ✅ Clearer `app/pipeline/` structure
- ✅ Grouped by domain (trending, comments, channels, etc.)
- ✅ Easier to test individual pipelines

### After Phase 3 (Future - 6 hours)
- ✅ Fewer files overall (70 → ~50)
- ✅ Consolidated related code
- ✅ Professional-looking structure

---

## Files to Update After Reorganization

### Makefile
```bash
# Find all references
grep "app.pipeline" Makefile

# Update like this:
# OLD: python -m app.pipeline.fetch_trending
# NEW: python -m app.pipeline.trending.fetch
```

### Test files
```bash
# Find all imports
grep -r "from app.pipeline" tests/

# Update imports
# OLD: from app.pipeline.fetch_trending import fetch
# NEW: from app.pipeline.trending.fetch import fetch
```

### Other pipeline files
```bash
# Find cross-references
grep -r "from app.pipeline" app/

# Update as needed
```

---

## Pro Tips

1. **Use git mv** to preserve history:
   ```bash
   git mv app/pipeline/fetch_trending.py app/pipeline/trending/fetch.py
   ```

2. **Find all imports** before renaming:
   ```bash
   grep -r "from app.pipeline.fetch_trending" . | grep -v __pycache__
   ```

3. **Update in small batches**:
   - Move 1 subdirectory at a time
   - Test after each move
   - Commit after each successful test

4. **Create __init__.py** files:
   ```bash
   find app/ -type d -exec touch {}/__init__.py \;
   ```

5. **Use search & replace** in VS Code:
   - Find: `from app.pipeline.fetch_trending`
   - Replace: `from app.pipeline.trending.fetch`

---

## Quick Decision Matrix

| Change | Time | Risk | Value | Priority |
|--------|------|------|-------|----------|
| Delete duplicates | 5 min | Zero | Medium | **DO NOW** |
| Delete empty dirs | 2 min | Zero | Low | **DO NOW** |
| Organize analysis/ | 2 hrs | Low | High | **This Week** |
| Organize pipeline/ | 4 hrs | Med | High | **Next Week** |
| Consolidate DTOs | 3 hrs | Low | Medium | Later |
| Consolidate API | 3 hrs | Med | Low | Optional |

---

## Get Help

If you need help with:
- **Finding imports**: `grep -r "from app.X" .`
- **Testing**: `python -m pytest tests/`
- **Makefile**: Check targets with `make -n fetch-trending`
- **Rollback**: `git checkout app/`

See **APP_ANALYSIS.md** for detailed analysis and migration plan.
