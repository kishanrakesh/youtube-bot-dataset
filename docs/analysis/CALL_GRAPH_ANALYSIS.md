# Comprehensive Call Graph Analysis

**Generated:** 2025-11-14  
**Purpose:** Identify code used by Makefile entry points to make project lean

## Summary

Based on analysis of Makefile entry points and their imports:

| Metric | Count |
|--------|-------|
| Total Python files in `app/` | 55 |
| **Files used by Makefile** | **~35** |
| Files potentially unused | **~20** |
| Usage rate | **~64%** |

---

## Makefile Entry Points

```makefile
fetch-trending       → app.pipeline.trending.fetch
load-trending        → app.pipeline.trending.load  
fetch-comments       → app.pipeline.comments.fetch
register-commenters  → app.pipeline.comments.register
capture-screenshots  → app.pipeline.screenshots.capture
review               → app.pipeline.screenshots.review
```

---

## Dependency Tree (Level 1-3)

### 1. `fetch-trending` → `app/pipeline/trending/fetch.py`
```
app/pipeline/trending/fetch.py
├── app/youtube_api/fetch_trending_videos_general.py
│   ├── app/utils/clients.py (get_youtube)
│   ├── app/utils/gcs_utils.py
│   ├── app/utils/paths.py  
│   └── app/utils/manifest_utils.py
└── app/youtube_api/fetch_trending_videos_by_category.py
    ├── app/utils/clients.py
    ├── app/utils/gcs_utils.py
    ├── app/utils/paths.py
    └── app/utils/manifest_utils.py
```

### 2. `load-trending` → `app/pipeline/trending/load.py`
```
app/pipeline/trending/load.py
├── app/env.py
├── app/utils/gcs_utils.py
└── app/utils/paths.py
```

### 3. `fetch-comments` → `app/pipeline/comments/fetch.py`
```
app/pipeline/comments/fetch.py
├── app/youtube_api/fetch_comment_threads_by_video_id.py
│   ├── app/utils/clients.py
│   ├── app/utils/gcs_utils.py
│   └── app/utils/paths.py
└── app/pipeline/trending/load.py (see #2)
```

### 4. `register-commenters` → `app/pipeline/comments/register.py`
```
app/pipeline/comments/register.py
├── app/utils/gcs_utils.py
└── app/pipeline/comments/register_channels.py
    ├── app/utils/image_processing.py
    │   └── (ML models, cv2, numpy)
    ├── app/utils/manifest_utils.py
    └── app/pipeline/channels/scraping.py
        ├── app/utils/clients.py
        ├── app/utils/gcs_utils.py
        ├── app/utils/image_processing.py
        └── app/youtube_api/fetch_channels_by_id.py
            ├── app/utils/clients.py
            └── app/utils/youtube_helpers.py
```

### 5. `capture-screenshots` → `app/pipeline/screenshots/capture.py`
```
app/pipeline/screenshots/capture.py
├── app/utils/gcs_utils.py
└── app/pipeline/channels/scraping.py (see #4)
```

### 6. `review` → `app/pipeline/screenshots/review.py`
```
app/pipeline/screenshots/review.py
├── app/pipeline/screenshots/review_ui.py
│   └── (cv2, firestore, gcs)
└── app/pipeline/channels/scraping.py (see #4)
```

---

## ✅ Files USED by Makefile (Core System)

### Entry Points (6 files)
- `app/pipeline/trending/fetch.py`
- `app/pipeline/trending/load.py`
- `app/pipeline/comments/fetch.py`
- `app/pipeline/comments/register.py`
- `app/pipeline/screenshots/capture.py`
- `app/pipeline/screenshots/review.py`

### Core Pipeline (4 files)
- `app/pipeline/comments/register_channels.py` ⭐
- `app/pipeline/channels/scraping.py` ⭐ (high complexity)
- `app/pipeline/screenshots/review_ui.py`
- `app/env.py`

### YouTube API (5 files)
- `app/youtube_api/fetch_trending_videos_general.py`
- `app/youtube_api/fetch_trending_videos_by_category.py`
- `app/youtube_api/fetch_comment_threads_by_video_id.py`
- `app/youtube_api/fetch_channels_by_id.py`
- `app/youtube_api/__init__.py`

### Utilities (8 files)
- `app/utils/clients.py`
- `app/utils/gcs_utils.py`
- `app/utils/paths.py`
- `app/utils/manifest_utils.py` ⭐ (newly refactored)
- `app/utils/image_processing.py`
- `app/utils/youtube_helpers.py`
- `app/utils/logging.py`
- `app/utils/__init__.py`

### __init__ files (5 files)
- `app/__init__.py`
- `app/pipeline/__init__.py`
- `app/pipeline/trending/__init__.py`
- `app/pipeline/comments/__init__.py`
- `app/pipeline/screenshots/__init__.py`

**USED Files Total: ~35 files**

---

## 🗑️ Files POTENTIALLY UNUSED (Can be archived/removed)

### Analysis & Evaluation (NOT in Makefile) - 7 files
- `app/analysis/evaluation/compare_avatar_metrics.py`
- `app/analysis/evaluation/rank_bot_candidates.py`
- `app/analysis/evaluation/suggest_thresholds.py`
- `app/analysis/inference/classifier_utils.py`
- `app/analysis/inference/score_channels.py`
- `app/analysis/visualization/visualize_clusters.py`
- `app/analysis/export_script.py`

**Recommendation:** Move to `archive/analysis/` - these appear to be one-off analysis scripts

### Bot Detection (NOT in Makefile) - 1 file
- `app/pipeline/bot_detection/backfill.py`

**Recommendation:** Check if used manually, otherwise archive

### Channel Operations (NOT in Makefile) - 2 files
- `app/pipeline/channels/backfill.py`
- `app/pipeline/channels/cleanup.py`

**Recommendation:** These may be manual utility scripts - verify before removing

### Domain Resolution (NOT in Makefile) - 1 file
- `app/pipeline/domains/resolve.py`

**Recommendation:** Archive if not used

### Data Models (NOT used) - 5 files
- `app/models/channels.py`
- `app/models/comments.py`
- `app/models/domains.py`
- `app/models/edges.py`
- `app/models/videos.py`

**Recommendation:** Keep if planning to add type safety, otherwise remove

### YouTube API (unused) - 3 files
- `app/youtube_api/fetch_channel_sections.py`
- `app/youtube_api/fetch_videos_by_channel.py`
- `app/youtube_api/fetch_videos_by_id.py`

**Recommendation:** Archive - may be useful for future features

### BigQuery & Other - 2 files
- `app/bigquery_schemas.py`
- `app/utils/json_utils.py`

**Recommendation:** Archive if not used

**UNUSED Files Total: ~20 files**

---

## Recommendations for Making Project Lean

### Phase 1: Archive Unused Code (Low Risk)
```bash
mkdir -p archive/{analysis,models,youtube_api_extra}

# Move analysis scripts
mv app/analysis/ archive/

# Move unused models
mv app/models/ archive/

# Move unused YouTube API
mv app/youtube_api/fetch_channel_sections.py archive/youtube_api_extra/
mv app/youtube_api/fetch_videos_by_channel.py archive/youtube_api_extra/
mv app/youtube_api/fetch_videos_by_id.py archive/youtube_api_extra/

# Move bigquery
mv app/bigquery_schemas.py archive/
```

**Expected Impact:**  
- Remove ~20 files (~36% of codebase)
- Clearer project structure
- Faster imports and IDE performance

### Phase 2: Verify Manual Scripts
Check if these are used outside Makefile:
- `app/pipeline/bot_detection/backfill.py`
- `app/pipeline/channels/backfill.py`
- `app/pipeline/channels/cleanup.py`
- `app/pipeline/domains/resolve.py`

### Phase 3: Refactor Complex Functions (Already Started!)
Focus on:
- ✅ `ManifestManager` - Created
- ⏭️ `expand_bot_graph_async()` - Complexity 29
- ⏭️ `backfill_channel()` - Complexity 27

---

##  Next Steps

1. **Review unused files list** - Verify nothing critical
2. **Create archive/ directory** - Don't delete, just move
3. **Test Makefile commands** - Ensure all still work
4. **Update documentation** - Reflect new structure
5. **Continue refactoring** - Tackle high complexity functions

---

## Key Insights

- **Core system is ~35 files** (64% of app/)
- **Main dependencies:** GCS utils, YouTube API clients, Playwright scraping
- **Highest complexity:** `app/pipeline/channels/scraping.py`
- **Most refactored:** `app/utils/manifest_utils.py` ✅
- **Unused code:** Primarily analysis scripts and data models

