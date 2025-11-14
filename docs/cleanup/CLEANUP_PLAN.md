# App Directory Cleanup Plan

## Current Issues

### 1. **Duplicate Directories** ❌
- `app/pipeline/pipeline/` - Duplicate of `app/pipeline/`
- `app/screenshots/screenshots/` - Duplicate of `app/screenshots/`

### 2. **Empty/Unused Directories** ⚠️
- `app/bigquery/` - Empty
- `app/config/` - Empty
- `app/gcs/` - Empty  
- `app/parser/` - Empty

### 3. **Unclear Organization** 🤔
- `app/analysis/` - Mix of training and analysis scripts
- `app/labelling/` - Only 1 file
- `app/orchestration/` - Only 1 file

## Proposed Structure

```
app/
├── __init__.py
├── env.py                    # Environment config
├── bigquery_schemas.py       # BigQuery schemas
│
├── core/                     # NEW: Core business logic
│   ├── __init__.py
│   ├── models/              # Renamed from models/ (DTOs)
│   │   ├── __init__.py
│   │   ├── channel.py       # Consolidated channel DTOs
│   │   ├── video.py         # Consolidated video DTOs
│   │   ├── comment.py
│   │   ├── domain.py
│   │   └── labels.py
│   └── schemas/             # NEW: BigQuery schemas
│       ├── __init__.py
│       └── bigquery_schemas.py
│
├── data/                    # NEW: Data layer (pipelines)
│   ├── __init__.py
│   ├── youtube/            # Renamed from youtube_api/
│   │   ├── __init__.py
│   │   ├── channels.py     # fetch_channels_by_id, fetch_channel_sections
│   │   ├── videos.py       # fetch_videos_by_id, fetch_videos_by_channel
│   │   ├── comments.py     # fetch_comment_threads_by_video_id
│   │   └── trending.py     # fetch_trending_videos_*
│   ├── pipelines/          # Renamed from pipeline/
│   │   ├── __init__.py
│   │   ├── trending.py     # fetch_trending, load_trending
│   │   ├── comments.py     # fetch_video_comments, register_commenters
│   │   ├── channels.py     # backfill_channels, cleanup_handles
│   │   ├── screenshots.py  # capture_screenshots
│   │   ├── bot_detection.py # backfill_probabilities, expand_bot_graph
│   │   └── domains.py      # resolve_channel_domains
│   └── screenshots/        # Keep as-is (remove duplicate)
│       ├── __init__.py
│       ├── capture_channel_screenshots.py
│       └── register_commenter_channels.py
│
├── analysis/               # Keep: Bot analysis & ML
│   ├── __init__.py
│   ├── classifiers/        # NEW: Classifier logic
│   │   ├── __init__.py
│   │   ├── kmeans_pca.py   # train_kmeans_pca
│   │   └── utils.py        # classifier_utils
│   ├── scoring/            # NEW: Scoring & ranking
│   │   ├── __init__.py
│   │   ├── score_channels.py
│   │   ├── rank_bot_candidates.py
│   │   └── ranking_model.py
│   ├── visualization/      # NEW: Viz & reporting
│   │   ├── __init__.py
│   │   ├── visualize_clusters.py
│   │   └── compare_avatar_metrics.py
│   ├── export_script.py
│   └── suggest_thresholds.py
│
├── labelling/              # Keep: Human labeling tools
│   ├── __init__.py
│   └── review_channel_screenshots.py
│
├── orchestration/          # Keep: Workflow orchestration
│   ├── __init__.py
│   └── pipelines.py
│
└── utils/                  # Keep: Shared utilities
    ├── __init__.py
    ├── clients.py
    ├── gcs_utils.py
    ├── image_processing.py
    ├── json_utils.py
    ├── logging.py
    ├── manifest_utils.py
    ├── paths.py
    └── youtube_helpers.py
```

## Migration Steps

### Phase 1: Remove Duplicates
```bash
# Remove duplicate directories
rm -rf app/pipeline/pipeline/
rm -rf app/screenshots/screenshots/

# Remove empty directories
rmdir app/bigquery app/config app/gcs app/parser 2>/dev/null
```

### Phase 2: Consolidate DTOs (models/)
```bash
# Rename models/ to core/models/
mkdir -p app/core/models
mv app/models/*.py app/core/models/

# Optional: Consolidate related DTOs into single files
# Example: Channel*.py → channel.py
```

### Phase 3: Reorganize youtube_api/
```bash
# Rename youtube_api/ to data/youtube/
mkdir -p app/data/youtube
mv app/youtube_api/* app/data/youtube/

# Optional: Consolidate by resource type
```

### Phase 4: Reorganize pipelines/
```bash
# Rename pipeline/ to data/pipelines/
mkdir -p app/data/pipelines
mv app/pipeline/*.py app/data/pipelines/

# Optional: Group by functionality
```

### Phase 5: Reorganize analysis/
```bash
# Create subdirectories
mkdir -p app/analysis/{classifiers,scoring,visualization}

# Move files
mv app/analysis/train_kmeans_pca.py app/analysis/classifiers/kmeans_pca.py
mv app/analysis/classifier_utils.py app/analysis/classifiers/utils.py
# ... etc
```

## Import Updates Needed

After restructure, update imports:

### Before:
```python
from app.models.ChannelDTO import ChannelDTO
from app.youtube_api.fetch_channels_by_id import fetch_channels
from app.pipeline.fetch_trending import fetch_trending
```

### After:
```python
from app.core.models.channel import ChannelDTO
from app.data.youtube.channels import fetch_channels
from app.data.pipelines.trending import fetch_trending
```

## Benefits

1. ✅ **Clearer separation**:
   - `core/` - Business models & schemas
   - `data/` - Data access & pipelines
   - `analysis/` - ML & analytics
   - `utils/` - Shared utilities

2. ✅ **No duplicates**:
   - Removed nested duplicate directories
   - Removed empty directories

3. ✅ **Better organization**:
   - Related files grouped together
   - Easier to find code
   - Logical module hierarchy

4. ✅ **Scalability**:
   - Easy to add new modules
   - Clear where new code belongs

## Rollback

If anything breaks:
```bash
git checkout app/
# Or restore from backup
```

## Testing After Migration

```bash
# Test imports
python -c "from app.core.models.channel import ChannelDTO"
python -c "from app.data.youtube.channels import fetch_channels"

# Run tests
python -m pytest tests/
```
