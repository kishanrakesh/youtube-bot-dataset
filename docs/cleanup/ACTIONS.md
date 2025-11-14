# Action Plan: Clean Up app/ Directory

## Overview

This document provides concrete, copy-paste commands to restructure your `app/` directory.

**Time required**: 5 minutes to 2 days (depending on scope)  
**Risk level**: Low to Medium (phases 1-2 are zero risk)

---

## Phase 1: Quick Wins (5 minutes, ZERO RISK) ⚡

### What This Does
- Removes duplicate directories
- Removes empty directories
- No code changes, no import changes
- 100% safe

### Commands

```bash
cd /root/youtube-bot-dataset

# Backup first (optional but recommended)
git add -A
git commit -m "Backup before cleanup"

# Remove duplicate nested directories
echo "🗑️  Removing duplicate directories..."
rm -rf app/pipeline/pipeline/
rm -rf app/screenshots/screenshots/

# Remove empty directories
echo "🗑️  Removing empty directories..."
rmdir app/bigquery app/config app/gcs app/parser 2>/dev/null || true

# Verify nothing broke
echo "✅ Testing imports..."
python -c "from app.utils.clients import get_youtube" && echo "  ✓ Utils work"
python -c "from app.models.ChannelDTO import ChannelDTO" && echo "  ✓ Models work"
python -c "from app.pipeline.fetch_trending import fetch_trending_videos" && echo "  ✓ Pipeline works"

echo "✅ Phase 1 complete! 6 directories removed, 0 code changes."
```

### Expected Output
```
🗑️  Removing duplicate directories...
🗑️  Removing empty directories...
✅ Testing imports...
  ✓ Utils work
  ✓ Models work
  ✓ Pipeline works
✅ Phase 1 complete! 6 directories removed, 0 code changes.
```

### Commit
```bash
git add -A
git commit -m "Clean up app/: remove duplicates and empty directories"
```

**STOP HERE** if you only want quick wins. Everything else is optional.

---

## Phase 2: Organize Analysis (2 hours, LOW RISK) 📊

### What This Does
- Creates subdirectories in `app/analysis/`
- Groups files by purpose: training, inference, evaluation, visualization
- Few imports to update (mostly standalone scripts)

### Step 1: Create New Structure

```bash
cd /root/youtube-bot-dataset/app/analysis

# Create subdirectories
mkdir -p training inference evaluation visualization

# Add __init__.py files
touch training/__init__.py
touch inference/__init__.py
touch evaluation/__init__.py
touch visualization/__init__.py
```

### Step 2: Move Files

```bash
cd /root/youtube-bot-dataset/app/analysis

# Training files
git mv train_kmeans_pca.py training/
git mv ranking_model.py training/train_xgboost.py

# Inference files
git mv classifier_utils.py inference/
git mv score_channels.py inference/

# Evaluation files
git mv rank_bot_candidates.py evaluation/
git mv suggest_thresholds.py evaluation/
git mv compare_avatar_metrics.py evaluation/

# Visualization files
git mv visualize_clusters.py visualization/

# Keep export_script.py at top level
```

### Step 3: Update Imports

**Find files that import from analysis:**
```bash
cd /root/youtube-bot-dataset
grep -r "from app.analysis" . --include="*.py" | grep -v __pycache__ | cut -d: -f1 | sort -u
```

**Update these files:**

In `app/utils/image_processing.py`:
```python
# OLD
from app.analysis.classifier_utils import score_with_pca_kmeans

# NEW
from app.analysis.inference.classifier_utils import score_with_pca_kmeans
```

In any training scripts:
```python
# OLD
from app.analysis.ranking_model import train_xgb

# NEW
from app.analysis.training.train_xgboost import train_xgb
```

### Step 4: Test

```bash
# Test imports
python -c "from app.analysis.inference.classifier_utils import get_pca_kmeans_model"
python -c "from app.analysis.training.train_kmeans_pca import main"
python -c "from app.analysis.evaluation.rank_bot_candidates import main"
python -c "from app.analysis.visualization.visualize_clusters import main"

# Run a training script
python -m app.analysis.training.train_kmeans_pca

# Check for broken imports
grep -r "from app.analysis.classifier_utils" . --include="*.py" | grep -v __pycache__
# Should return nothing (or files you haven't updated yet)
```

### Step 5: Commit

```bash
git add -A
git commit -m "Organize app/analysis/: separate training, inference, evaluation, viz"
```

---

## Phase 3: Organize Pipeline (4 hours, MEDIUM RISK) 🔄

### What This Does
- Creates subdirectories in `app/pipeline/` by domain
- Groups related pipelines together
- Updates Makefile and imports

### Step 1: Create New Structure

```bash
cd /root/youtube-bot-dataset/app/pipeline

# Create subdirectories
mkdir -p trending comments channels screenshots domains bot_detection

# Add __init__.py files
touch trending/__init__.py
touch comments/__init__.py
touch channels/__init__.py
touch screenshots/__init__.py
touch domains/__init__.py
touch bot_detection/__init__.py
```

### Step 2: Move Files

```bash
cd /root/youtube-bot-dataset/app/pipeline

# Trending pipelines
git mv fetch_trending.py trending/fetch.py
git mv load_trending.py trending/load.py

# Comment pipelines
git mv fetch_video_comments.py comments/fetch.py
git mv register_commenters.py comments/register.py

# Channel pipelines
git mv backfill_channels.py channels/backfill.py
git mv cleanup_handles.py channels/cleanup.py
git mv expand_bot_graph.py channels/scraping.py

# Screenshot pipelines
git mv capture_screenshots.py screenshots/capture.py
git mv review_channels.py screenshots/review.py

# Domain pipelines
git mv resolve_channel_domains.py domains/resolve.py

# Bot detection pipelines
git mv backfill_probabilities.py bot_detection/backfill.py
```

### Step 3: Update Makefile

```bash
cd /root/youtube-bot-dataset
```

Edit `Makefile` and replace:

```makefile
# BEFORE
fetch-trending:
	python -m app.pipeline.fetch_trending \
		--region $(TRENDING_REGION) \
		--category $(CATEGORY)

load-trending:
	python -m app.pipeline.load_trending \
		--region $(TRENDING_REGION)

fetch-comments:
	python -m app.pipeline.fetch_video_comments \
		--region $(TRENDING_REGION)

register-commenters:
	python -m app.pipeline.register_commenters \
		--limit $(REVIEW_LIMIT)

capture-screenshots:
	python -m app.pipeline.capture_screenshots \
		--limit $(SCREENSHOT_LIMIT)

review:
	python -m app.pipeline.review_channels \
		--limit $(REVIEW_LIMIT)
```

```makefile
# AFTER
fetch-trending:
	python -m app.pipeline.trending.fetch \
		--region $(TRENDING_REGION) \
		--category $(CATEGORY)

load-trending:
	python -m app.pipeline.trending.load \
		--region $(TRENDING_REGION)

fetch-comments:
	python -m app.pipeline.comments.fetch \
		--region $(TRENDING_REGION)

register-commenters:
	python -m app.pipeline.comments.register \
		--limit $(REVIEW_LIMIT)

capture-screenshots:
	python -m app.pipeline.screenshots.capture \
		--limit $(SCREENSHOT_LIMIT)

review:
	python -m app.pipeline.screenshots.review \
		--limit $(REVIEW_LIMIT)
```

### Step 4: Update Imports in Other Files

**Find all imports:**
```bash
grep -r "from app.pipeline" . --include="*.py" | grep -v __pycache__ | grep -v "app/pipeline/"
```

**Update each file found:**

Example in `app/orchestration/pipelines.py`:
```python
# OLD
from app.pipeline.fetch_trending import fetch_trending_videos

# NEW
from app.pipeline.trending.fetch import fetch_trending_videos
```

Example in `tests/`:
```python
# OLD
from app.pipeline.fetch_video_comments import fetch_comments

# NEW
from app.pipeline.comments.fetch import fetch_comments
```

### Step 5: Test

```bash
# Test imports
python -c "from app.pipeline.trending.fetch import fetch_trending_videos"
python -c "from app.pipeline.comments.register import register_commenter_channels"
python -c "from app.pipeline.screenshots.capture import fetch_channels_needing_screenshots"

# Test Makefile targets
make -n fetch-trending
make -n register-commenters

# Run a small test
make fetch-trending TRENDING_PAGES=1

# Check for broken imports
grep -r "from app.pipeline.fetch_trending" . --include="*.py" | grep -v __pycache__
# Should return nothing
```

### Step 6: Commit

```bash
git add -A
git commit -m "Organize app/pipeline/: group by domain (trending, comments, channels, etc.)"
```

---

## Phase 4: Consolidate DTOs (3 hours, LOW RISK) 📦

### What This Does
- Reduces 13 DTO files to 5
- Groups related DTOs together
- Simplifies imports

### Step 1: Create Consolidated Files

```bash
cd /root/youtube-bot-dataset/app/models
```

Create `channel.py`:
```python
"""Channel-related DTOs."""
from app.models.ChannelDTO import *
from app.models.ChannelLabelDTO import *
from app.models.ChannelScreenshotDTO import *
from app.models.ChannelStatusDTO import *

# Re-export all
__all__ = [
    'ChannelDTO',
    'ChannelLabelDTO', 
    'ChannelScreenshotDTO',
    'ChannelStatusDTO',
]
```

Create `video.py`:
```python
"""Video-related DTOs."""
from app.models.VideoDTO import *
from app.models.VideoTagEdgeDTO import *
from app.models.VideoTopicCategoryEdgeDTO import *

__all__ = [
    'VideoDTO',
    'VideoTagEdgeDTO',
    'VideoTopicCategoryEdgeDTO',
]
```

Create `domain.py`:
```python
"""Domain-related DTOs."""
from app.models.DomainDTO import *
from app.models.DomainEnrichmentDTO import *
from app.models.ChannelDomainLinkDTO import *

__all__ = [
    'DomainDTO',
    'DomainEnrichmentDTO',
    'ChannelDomainLinkDTO',
]
```

Create `edges.py`:
```python
"""Edge/relationship DTOs."""
from app.models.ChannelDiscoveryEdgeDTO import *
from app.models.ChannelFeaturedEdgeDTO import *

__all__ = [
    'ChannelDiscoveryEdgeDTO',
    'ChannelFeaturedEdgeDTO',
]
```

Create `comment.py`:
```python
"""Comment-related DTOs."""
from app.models.CommentDTO import *

__all__ = ['CommentDTO']
```

### Step 2: Update Imports

**Find all DTO imports:**
```bash
grep -r "from app.models" . --include="*.py" | grep -v __pycache__ | cut -d: -f1 | sort -u
```

**Update each file:**
```python
# OLD
from app.models.ChannelDTO import ChannelDTO
from app.models.VideoDTO import VideoDTO

# NEW
from app.models.channel import ChannelDTO
from app.models.video import VideoDTO
```

### Step 3: Test

```bash
# Test imports
python -c "from app.models.channel import ChannelDTO"
python -c "from app.models.video import VideoDTO"
python -c "from app.models.domain import DomainDTO"

# Run tests
python -m pytest tests/ -v

# Check for old imports
grep -r "from app.models.ChannelDTO" . --include="*.py" | grep -v __pycache__
# Should return nothing
```

### Step 4: Clean Up (Optional)

Once everything works, you can delete the old files:
```bash
cd /root/youtube-bot-dataset/app/models
rm Channel*.py Video*.py Domain*.py CommentDTO.py
```

### Step 5: Commit

```bash
git add -A
git commit -m "Consolidate app/models/: 13 files → 5 files"
```

---

## Phase 5: Consolidate YouTube API (3 hours, MEDIUM RISK) 📺

**NOTE**: This phase is OPTIONAL. Current structure is fine.

### What This Does
- Reduces 7 API files to 4
- Groups by resource type

### Commands

```bash
cd /root/youtube-bot-dataset/app/youtube_api

# Create consolidated files
cat > channels.py << 'EOF'
"""Channel API wrappers."""
# Copy content from:
# - fetch_channels_by_id.py
# - fetch_channel_sections.py
EOF

cat > videos.py << 'EOF'
"""Video API wrappers."""
# Copy content from:
# - fetch_videos_by_id.py
# - fetch_videos_by_channel.py
EOF

cat > trending.py << 'EOF'
"""Trending API wrappers."""
# Copy content from:
# - fetch_trending_videos_by_category.py
# - fetch_trending_videos_general.py
EOF

cat > comments.py << 'EOF'
"""Comment API wrappers."""
# Copy content from:
# - fetch_comment_threads_by_video_id.py
EOF
```

Then update all imports from `app.youtube_api.*`

**Recommendation**: Skip this phase unless you really want consolidation.

---

## Testing Checklist

After each phase:

```bash
# ✅ Imports work
python -c "from app.utils.clients import get_youtube"
python -c "from app.models.channel import ChannelDTO"
python -c "from app.pipeline.trending.fetch import fetch_trending_videos"

# ✅ Tests pass
python -m pytest tests/ -v

# ✅ CLI works
python -m app.pipeline.trending.fetch --help

# ✅ Makefile works
make fetch-trending TRENDING_PAGES=1

# ✅ No broken imports
grep -r "from app.pipeline.fetch_trending" . --include="*.py" | grep -v __pycache__
# Should return nothing
```

---

## Rollback Instructions

If something breaks:

```bash
# See what changed
git status
git diff

# Rollback everything
git reset --hard HEAD

# Or rollback specific file
git checkout app/pipeline/fetch_trending.py

# Or rollback specific phase
git log --oneline | head -5
git reset --hard <commit-hash-before-phase>
```

---

## Summary Table

| Phase | Time | Risk | Files Changed | Benefit |
|-------|------|------|---------------|---------|
| 1: Quick Wins | 5 min | Zero | 0 | Clean structure |
| 2: Organize Analysis | 2 hrs | Low | ~5 imports | Clear ML organization |
| 3: Organize Pipeline | 4 hrs | Med | ~15 imports + Makefile | Clear pipeline organization |
| 4: Consolidate DTOs | 3 hrs | Low | ~30 imports | Fewer files |
| 5: Consolidate API | 3 hrs | Med | ~20 imports | Optional |

**Total**: 5 min to 12+ hours depending on scope

---

## Recommended Approach

### Conservative (Low Risk)
1. ✅ Phase 1 only (5 min)
2. Stop here, celebrate clean structure

### Moderate (Good ROI)
1. ✅ Phase 1 (5 min)
2. ✅ Phase 2 (2 hrs)
3. Stop here, you've organized the key modules

### Aggressive (Full Cleanup)
1. ✅ Phase 1 (5 min)
2. ✅ Phase 2 (2 hrs)
3. ✅ Phase 3 (4 hrs)
4. ✅ Phase 4 (3 hrs)
5. ⚠️ Phase 5 (optional)

---

## Getting Help

If you get stuck:

1. **Check imports**: `grep -r "from app.X" . --include="*.py"`
2. **Run tests**: `python -m pytest tests/ -v`
3. **Check git**: `git status`, `git diff`
4. **Rollback**: `git reset --hard HEAD`
5. **Read docs**: `APP_ANALYSIS.md` for details

---

## Next Steps

1. ✅ **Read this document**
2. ✅ **Backup your code**: `git commit -am "Backup before cleanup"`
3. ✅ **Run Phase 1**: Copy-paste commands above (5 min)
4. 🤔 **Decide**: Do you want to continue with Phase 2+?
5. 🚀 **Execute**: One phase at a time, test after each

Good luck! 🎉
