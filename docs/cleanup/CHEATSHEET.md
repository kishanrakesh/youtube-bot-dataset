# App Directory Cleanup - One-Page Cheat Sheet

## 🚨 Critical Issues (Fix NOW)

```bash
# 5 MINUTES - ZERO RISK
cd /root/youtube-bot-dataset
rm -rf app/pipeline/pipeline/      # Duplicate directory
rm -rf app/screenshots/screenshots/ # Duplicate directory
rmdir app/bigquery app/config app/gcs app/parser  # Empty directories
git commit -am "Clean up app/: remove duplicates and empties"
```

## 📊 Current Problems

| Issue | Severity | Impact | Fix Time |
|-------|----------|--------|----------|
| Duplicate dirs (`pipeline/pipeline/`) | 🔴 Critical | Confusion | 2 min |
| Empty dirs (4 total) | 🟡 Medium | Clutter | 2 min |
| Mixed concerns in `analysis/` | 🟡 Medium | Hard to navigate | 2 hrs |
| Mixed concerns in `pipeline/` | 🟡 Medium | Hard to navigate | 4 hrs |
| Too many DTO files (13) | 🟢 Low | Minor annoyance | 3 hrs |

## 🎯 Cleanup Phases

```
Phase 1: Quick Wins          →  5 min   | Zero risk  | DELETE duplicates/empties
Phase 2: Organize Analysis   →  2 hrs   | Low risk   | CREATE subdirs in analysis/
Phase 3: Organize Pipeline   →  4 hrs   | Med risk   | CREATE subdirs in pipeline/
Phase 4: Consolidate DTOs    →  3 hrs   | Low risk   | MERGE 13 files → 5
Phase 5: Consolidate API     →  3 hrs   | Med risk   | OPTIONAL
```

## 📁 Before → After

### Analysis Directory
```
BEFORE: 8 files flat          AFTER: 8 files in 4 subdirs
analysis/                     analysis/
├── classifier_utils.py       ├── training/
├── score_channels.py         │   ├── train_kmeans_pca.py
├── train_kmeans_pca.py       │   └── train_xgboost.py
├── ranking_model.py          ├── inference/
├── rank_bot_candidates.py    │   ├── classifier_utils.py
├── suggest_thresholds.py     │   └── score_channels.py
├── compare_avatar_metrics.py ├── evaluation/
└── visualize_clusters.py     │   ├── rank_bot_candidates.py
                              │   ├── suggest_thresholds.py
                              │   └── compare_avatar_metrics.py
                              ├── visualization/
                              │   └── visualize_clusters.py
                              └── export_script.py
```

### Pipeline Directory
```
BEFORE: 13 files flat         AFTER: 13 files in 6 subdirs
pipeline/                     pipeline/
├── fetch_trending.py         ├── trending/
├── load_trending.py          │   ├── fetch.py
├── fetch_video_comments.py   │   └── load.py
├── register_commenters.py    ├── comments/
├── backfill_channels.py      │   ├── fetch.py
├── cleanup_handles.py        │   └── register.py
├── expand_bot_graph.py       ├── channels/
├── capture_screenshots.py    │   ├── backfill.py
├── review_channels.py        │   ├── cleanup.py
├── resolve_channel_domains.py│   └── scraping.py
├── backfill_probabilities.py ├── screenshots/
└── pipeline/ [DUPLICATE]     │   ├── capture.py
                              │   └── review.py
                              ├── domains/
                              │   └── resolve.py
                              └── bot_detection/
                                  └── backfill.py
```

### Models Directory (Optional)
```
BEFORE: 13 files              AFTER: 5 files
models/                       models/
├── ChannelDTO.py             ├── channel.py     [All Channel* DTOs]
├── ChannelLabelDTO.py        ├── video.py       [All Video* DTOs]
├── ChannelScreenshotDTO.py   ├── comment.py
├── ChannelStatusDTO.py       ├── domain.py      [Domain + Enrichment]
├── ChannelDiscoveryEdgeDTO.py└── edges.py       [Discovery/Featured]
├── ChannelDomainLinkDTO.py
├── ChannelFeaturedEdgeDTO.py
├── CommentDTO.py
├── DomainDTO.py
├── DomainEnrichmentDTO.py
├── VideoDTO.py
├── VideoTagEdgeDTO.py
└── VideoTopicCategoryEdgeDTO.py
```

## 🔧 Import Changes

### Phase 2: Analysis
```python
# OLD
from app.analysis.classifier_utils import score_with_pca_kmeans

# NEW
from app.analysis.inference.classifier_utils import score_with_pca_kmeans
```

### Phase 3: Pipeline
```python
# OLD
from app.pipeline.fetch_trending import fetch_trending_videos

# NEW
from app.pipeline.trending.fetch import fetch_trending_videos
```

### Phase 4: Models
```python
# OLD
from app.models.ChannelDTO import ChannelDTO

# NEW
from app.models.channel import ChannelDTO
```

## ✅ Testing Checklist

After each phase:
```bash
# 1. Test imports
python -c "from app.utils.clients import get_youtube"
python -c "from app.pipeline.trending.fetch import fetch_trending_videos"

# 2. Run tests
python -m pytest tests/ -v

# 3. Test CLI
make fetch-trending TRENDING_PAGES=1

# 4. Check for broken imports
grep -r "from app.pipeline.fetch_trending" . --include="*.py" | grep -v __pycache__
```

## 🔄 Rollback

If something breaks:
```bash
git status         # See what changed
git diff          # See specific changes
git reset --hard HEAD  # Undo everything
```

## 📚 Documentation

| File | Purpose | Length |
|------|---------|--------|
| `APP_DOCS_INDEX.md` | Navigation guide | 1 page |
| `APP_ANALYSIS.md` | Deep analysis | 15 pages |
| `CLEANUP_QUICKSTART.md` | Quick reference | 3 pages |
| `APP_STRUCTURE_VISUAL.md` | Visual diagrams | 5 pages |
| `CLEANUP_ACTIONS.md` | Step-by-step commands | 8 pages |
| `APP_CLEANUP_CHEATSHEET.md` | This file | 1 page |

## 🎯 Decision Guide

**I have 5 minutes:**
→ Do Phase 1 only (delete duplicates/empties)

**I have 2 hours:**
→ Do Phase 1 + 2 (organize analysis/)

**I have a day:**
→ Do Phase 1 + 2 + 3 (organize pipeline/)

**I want it perfect:**
→ Do all 5 phases (full cleanup)

**I'm not sure:**
→ Read `CLEANUP_QUICKSTART.md` first

## 📊 Risk Assessment

| Phase | Time | Risk | Benefit | Recommendation |
|-------|------|------|---------|----------------|
| 1: Quick wins | 5m | 🟢 Zero | Medium | **DO NOW** |
| 2: Analysis | 2h | 🟢 Low | High | **This week** |
| 3: Pipeline | 4h | 🟡 Med | High | **Next week** |
| 4: DTOs | 3h | 🟢 Low | Medium | Later |
| 5: API | 3h | 🟡 Med | Low | Optional |

## 🏁 Quick Start

```bash
# 1. Backup
git commit -am "Backup before cleanup"

# 2. Phase 1 (5 min, zero risk)
cd /root/youtube-bot-dataset
rm -rf app/pipeline/pipeline/ app/screenshots/screenshots/
rmdir app/bigquery app/config app/gcs app/parser 2>/dev/null
git commit -am "Phase 1: Remove duplicates and empties"

# 3. Test
python -c "from app.utils.clients import get_youtube" && echo "✅ Success!"

# 4. Decide: Continue with Phase 2?
```

## 💡 Pro Tips

1. **Use git mv** to preserve history:
   ```bash
   git mv old_file.py new_file.py
   ```

2. **Find all imports** before renaming:
   ```bash
   grep -r "from app.pipeline.fetch_trending" . --include="*.py"
   ```

3. **Update in batches**: Move 1 subdirectory at a time, test, commit

4. **Test after each change**: Don't batch multiple phases

5. **Read docs first**: 10 minutes of reading saves hours of fixing

## 📞 Help

Stuck? Check:
- `CLEANUP_ACTIONS.md` for detailed commands
- `APP_ANALYSIS.md` for risks & mitigation
- `git status` and `git diff` to see what changed
- `python -m pytest tests/` to validate

Rollback anytime: `git reset --hard HEAD`

---

**Ready?** Start with Phase 1 in `CLEANUP_ACTIONS.md` → Takes 5 minutes!
