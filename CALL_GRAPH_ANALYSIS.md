# Complete Call Graph Analysis for Makefile Commands

## Entry Point 1: `make fetch-trending`
**Entry:** `app.pipeline.trending.fetch.main()`

### Direct Dependencies:
1. `app.youtube_api.fetch_trending_videos_general.fetch_trending_videos_general()`
2. `app.youtube_api.fetch_trending_videos_by_category.fetch_trending_videos_by_category()`

### Files to Refactor:
- `app/youtube_api/fetch_trending_videos_general.py`
- `app/youtube_api/fetch_trending_videos_by_category.py`

---

## Entry Point 2: `make load-trending`
**Entry:** `app.pipeline.trending.load.main()`

### Direct Dependencies:
1. `app.utils.gcs_utils.read_json_from_gcs()`
2. `app.utils.paths.trending_video_raw_path()`
3. `app.env.GCS_BUCKET_DATA` (constant)

### Files to Refactor:
- `app/utils/gcs_utils.py` (read_json_from_gcs function)
- `app/utils/paths.py` (trending_video_raw_path function)

---

## Entry Point 3: `make fetch-comments`
**Entry:** `app.pipeline.comments.fetch.main()`

### Direct Dependencies:
1. `app.youtube_api.fetch_comment_threads_by_video_id.fetch_comment_threads_by_video_id()`
2. `app.pipeline.trending.load.main()` (already refactored)

### Files to Refactor:
- `app/youtube_api/fetch_comment_threads_by_video_id.py`

---

## Entry Point 4: `make register-commenters`
**Entry:** `app.pipeline.comments.register.main()`

### Direct Dependencies:
1. `app.pipeline.comments.register_channels.register_commenter_channels()` (async)
2. `app.utils.gcs_utils.list_gcs_files()`

### Files to Refactor:
- `app/pipeline/comments/register_channels.py` (large file, 484 lines)
- `app/utils/gcs_utils.py` (list_gcs_files function)

---

## Entry Point 5: `make capture-screenshots`
**Entry:** `app.pipeline.screenshots.capture.main()`

### Direct Dependencies:
1. `app.pipeline.channels.scraping.PlaywrightContext` (async context manager)
2. `app.pipeline.channels.scraping.get_channel_url()`
3. `app.utils.gcs_utils.upload_png()`
4. `google.cloud.firestore.Client`
5. `google.cloud.storage.Client`

### Files to Refactor:
- `app/pipeline/channels/scraping.py` (PlaywrightContext, get_channel_url)
- `app/utils/gcs_utils.py` (upload_png function)

---

## Entry Point 6: `make review`
**Entry:** `app.pipeline.screenshots.review.main()`

### Direct Dependencies:
1. `app.pipeline.channels.scraping.expand_bot_graph_async()` (async)
2. `app.pipeline.screenshots.review_ui.fetch_docs()`
3. `app.pipeline.screenshots.review_ui.review_docs()`

### Files to Refactor:
- `app/pipeline/channels/scraping.py` (expand_bot_graph_async)
- `app/pipeline/screenshots/review_ui.py` (fetch_docs, review_docs - large file, 350+ lines)

---

## Summary of Files Needing Refactoring

### High Priority (called by multiple entry points):
1. **`app/utils/gcs_utils.py`** - Used by: load-trending, register-commenters, capture-screenshots
   - Functions: `read_json_from_gcs()`, `list_gcs_files()`, `upload_png()`

2. **`app/pipeline/channels/scraping.py`** - Used by: capture-screenshots, review
   - Functions: `PlaywrightContext`, `get_channel_url()`, `expand_bot_graph_async()`

### YouTube API Functions:
3. **`app/youtube_api/fetch_trending_videos_general.py`**
4. **`app/youtube_api/fetch_trending_videos_by_category.py`**
5. **`app/youtube_api/fetch_comment_threads_by_video_id.py`**

### Pipeline Helpers:
6. **`app/pipeline/comments/register_channels.py`** (484 lines - large refactor)
7. **`app/pipeline/screenshots/review_ui.py`** (350+ lines - large refactor)

### Utilities:
8. **`app/utils/paths.py`** - Simple path generation functions

---

## Refactoring Priority Order

### Phase 1: Core Utilities (Most Reused)
1. `app/utils/gcs_utils.py` - 3 functions
2. `app/utils/paths.py` - Path generation
3. `app/pipeline/channels/scraping.py` - Playwright helpers

### Phase 2: YouTube API (Independent)
4. `app/youtube_api/fetch_trending_videos_general.py`
5. `app/youtube_api/fetch_trending_videos_by_category.py`
6. `app/youtube_api/fetch_comment_threads_by_video_id.py`

### Phase 3: Large Pipeline Files (Complex)
7. `app/pipeline/comments/register_channels.py` (484 lines)
8. `app/pipeline/screenshots/review_ui.py` (350+ lines)

---

## Estimated Scope
- **8 files** to refactor
- **~15-20 functions** total
- **~1500+ lines** of code to review and improve

