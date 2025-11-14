# Project Restructure Plan

## Current Issues
1. ❌ Root directory cluttered with data files (CSVs, PKL models)
2. ❌ `dataset.zip` and `dataset/` in root (should be in data/)
3. ❌ Model files scattered (root + models/ folder)
4. ❌ Multiple requirements files
5. ❌ Scripts and notebooks mixed with source code
6. ✅ Good: `app/` is well-structured with proper modules

## Proposed Structure

```
youtube-bot-dataset/
├── .env                          # Keep (environment config)
├── .gitignore                    # Keep
├── Dockerfile                    # Keep
├── Makefile                      # Keep
├── README.md                     # Add/update
├── requirements.txt              # Consolidate all requirements here
├── main.py                       # Keep (entry point)
│
├── app/                          # ✅ Keep as-is (well organized)
│   ├── __init__.py
│   ├── env.py
│   ├── bigquery_schemas.py
│   ├── analysis/
│   ├── bigquery/
│   ├── config/
│   ├── gcs/
│   ├── labelling/
│   ├── models/                   # DTOs
│   ├── orchestration/
│   ├── parser/
│   ├── pipeline/
│   ├── screenshots/
│   ├── utils/
│   └── youtube_api/
│
├── ml/                           # NEW: Machine learning code
│   ├── __init__.py
│   ├── training/
│   │   ├── __init__.py
│   │   ├── train_avatar_classifier.py       # From scripts/
│   │   ├── train_simple_avatar_classifier.py # From scripts/
│   │   └── estimate_training_time.py        # From scripts/
│   ├── inference/
│   │   ├── __init__.py
│   │   └── predict.py            # NEW: Inference code
│   ├── utils/
│   │   ├── __init__.py
│   │   └── export_avatar_dataset.py         # From scripts/
│   └── notebooks/
│       ├── train_avatar_colab.ipynb         # From root
│       └── COLAB_TRAINING_GUIDE.md          # From root
│
├── data/                         # NEW: All data files
│   ├── raw/                      # Raw data (if needed)
│   ├── processed/                # Processed data
│   │   ├── bot_metrics.csv       # From root
│   │   ├── channels_ranked.csv   # From root
│   │   └── channels_scored_xgb.csv # From root
│   ├── datasets/
│   │   ├── dataset.zip           # From root
│   │   └── avatar_images/        # Renamed from dataset/
│   │       ├── train/
│   │       └── val/
│   └── .gitignore                # Ignore large files
│
├── models/                       # Trained models
│   ├── avatar/                   # Avatar classification models
│   │   ├── rf_avatar_classifier.pkl
│   │   ├── xgb_avatar_classifier.pkl
│   │   ├── lr_avatar_classifier.pkl
│   │   └── svm_avatar_classifier.pkl
│   ├── clustering/
│   │   └── kmeans_pca_bot_model.pkl  # From root
│   ├── xgb_bot_model.pkl         # From root
│   └── .gitignore                # Don't commit large models
│
├── tests/                        # Renamed from test/
│   ├── __init__.py
│   ├── test_youtube_api_fetchers.py
│   ├── test_fetch_trending_and_comments.py
│   ├── test_playwright_render.py
│   ├── backfill_channel_metrics.py
│   └── run_annotation_tests.py
│
├── scripts/                      # Shell/utility scripts only
│   ├── run_nightly.sh            # From root
│   └── compare_envs.sh           # From root
│
├── config/                       # NEW: Configuration files
│   └── service-account.json      # From root (add to .gitignore!)
│
├── docs/                         # NEW: Documentation
│   └── architecture.md
│
└── results/                      # Keep (experiment outputs)
```

## Migration Steps (Safe - Won't Break Imports)

### Phase 1: Create New Structure (No Breaking Changes)
```bash
# Create new directories
mkdir -p ml/{training,inference,utils,notebooks}
mkdir -p data/{raw,processed,datasets}
mkdir -p models/{avatar,clustering}
mkdir -p config
mkdir -p docs
mv test tests  # Simple rename
```

### Phase 2: Move Files (Update Imports Where Needed)
```bash
# Move ML code
mv scripts/train_avatar_classifier.py ml/training/
mv scripts/train_simple_avatar_classifier.py ml/training/
mv scripts/estimate_training_time.py ml/training/
mv scripts/export_avatar_dataset.py ml/utils/
mv train_avatar_colab.ipynb ml/notebooks/
mv COLAB_TRAINING_GUIDE.md ml/notebooks/

# Move data files
mv bot_metrics.csv data/processed/
mv channels_ranked.csv data/processed/
mv channels_scored_xgb.csv data/processed/
mv dataset.zip data/datasets/
mv dataset data/datasets/avatar_images

# Move models
mv models/*.pkl models/avatar/ 2>/dev/null || true
mv kmeans_pca_bot_model.pkl models/clustering/
mv xgb_bot_model.pkl models/

# Move config
mv service-account.json config/

# Move scripts
mv run_nightly.sh scripts/
mv compare_envs.sh scripts/

# Clean up empty directories
rmdir scripts 2>/dev/null || true  # Old scripts folder if empty
```

### Phase 3: Update Imports
Only needed for moved ML scripts - change:
```python
# OLD (if they import from app)
from app.utils.something import func

# NEW (no change needed - app still in same place)
from app.utils.something import func
```

For scripts that become modules under `ml/`:
- Add `__init__.py` files
- Update any relative imports
- Can still run with: `python -m ml.training.train_avatar_classifier`

### Phase 4: Consolidate Requirements
```bash
# Merge all requirements into one
cat requirements.txt requirements-ml.txt requirements-missing.txt | sort -u > requirements_new.txt
mv requirements_new.txt requirements.txt
rm requirements-ml.txt requirements-missing.txt
```

### Phase 5: Update .gitignore
Add:
```
# Data
data/raw/*
data/datasets/*.zip
data/datasets/avatar_images/

# Models (large files)
models/**/*.pkl
models/**/*.pth
*.pkl
*.pth

# Config (secrets)
config/service-account.json
.env

# Environment
env/
env.old/
```

## Benefits

1. ✅ **Clear separation of concerns**
   - Production code: `app/`
   - ML/training code: `ml/`
   - Tests: `tests/`
   - Data: `data/`
   - Models: `models/`

2. ✅ **No import breakage**
   - `app/` stays exactly where it is
   - All existing imports continue to work

3. ✅ **Easier navigation**
   - Know where to find things
   - Clean root directory

4. ✅ **Better for collaboration**
   - Standard Python project structure
   - Easy to onboard new developers

5. ✅ **Git-friendly**
   - Proper .gitignore for data/models
   - Secrets in config/ folder

## Rollback Plan

If anything breaks:
```bash
git stash  # Save changes
git status  # See what moved
# Manually move back any problematic files
```

## Testing After Migration

```bash
# Test imports
python -c "from app.utils.clients import get_youtube"
python -c "from app.models.ChannelDTO import ChannelDTO"

# Test ML scripts
python -m ml.training.train_simple_avatar_classifier

# Run tests
python -m pytest tests/
```
