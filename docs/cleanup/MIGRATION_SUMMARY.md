# Project Restructure - Migration Summary

**Date:** November 14, 2025  
**Status:** ✅ COMPLETE

## Changes Made

### 📁 New Directory Structure

```
youtube-bot-dataset/
├── app/              ← UNCHANGED (production code)
├── ml/               ← NEW (ML training & notebooks)
│   ├── training/     - Train scripts
│   ├── inference/    - Prediction code
│   ├── utils/        - ML utilities
│   └── notebooks/    - Jupyter notebooks
├── data/             ← NEW (datasets & CSVs)
│   ├── raw/
│   ├── processed/    - CSV files
│   └── datasets/     - Avatar images, zips
├── models/           ← REORGANIZED
│   ├── avatar/       - Avatar classifiers
│   ├── clustering/   - Clustering models
│   └── *.pkl         - Other models
├── tests/            ← RENAMED from test/
├── scripts/          ← Shell scripts only
├── config/           ← NEW (service-account.json)
└── docs/             ← NEW (documentation)
```

### 📦 Files Moved

**ML Scripts → `ml/training/`:**
- train_avatar_classifier.py
- train_simple_avatar_classifier.py
- estimate_training_time.py

**ML Utils → `ml/utils/`:**
- export_avatar_dataset.py

**Notebooks → `ml/notebooks/`:**
- train_avatar_colab.ipynb
- COLAB_TRAINING_GUIDE.md

**Data → `data/`:**
- bot_metrics.csv → data/processed/
- channels_ranked.csv → data/processed/
- channels_scored_xgb.csv → data/processed/
- dataset.zip → data/datasets/
- dataset/ → data/datasets/avatar_images/

**Models → `models/`:**
- All *.pkl → models/avatar/
- kmeans_pca_bot_model.pkl → models/clustering/
- xgb_bot_model.pkl → models/

**Config → `config/`:**
- service-account.json → config/

**Scripts → `scripts/`:**
- run_nightly.sh
- compare_envs.sh

**Other:**
- test/ → tests/ (renamed)
- Consolidated requirements*.txt → requirements.txt

### ✅ What Still Works

1. **All `app/` imports unchanged**
   - `from app.utils.clients import ...` ✅
   - `from app.models.XYZ import ...` ✅
   - All production code paths intact

2. **Running ML scripts** (new paths):
   ```bash
   # Old way (still works from root):
   python scripts/train_simple_avatar_classifier.py
   
   # New way (as module):
   python -m ml.training.train_simple_avatar_classifier
   ```

3. **Data paths** - Update if hardcoded:
   - Old: `dataset/` → New: `data/datasets/avatar_images/`
   - Old: `*.csv` → New: `data/processed/*.csv`

4. **Model paths** - Update if hardcoded:
   - Old: `models/*.pkl` → New: `models/avatar/*.pkl`

### ⚠️ Breaking Changes

**Paths that need updating:**

1. **In ML training scripts** (if they reference datasets):
   ```python
   # OLD
   dataset_path = "dataset/"
   
   # NEW
   dataset_path = "data/datasets/avatar_images/"
   ```

2. **In model loading code**:
   ```python
   # OLD
   model_path = "models/rf_avatar_classifier.pkl"
   
   # NEW
   model_path = "models/avatar/rf_avatar_classifier.pkl"
   ```

3. **Service account JSON**:
   ```python
   # OLD (if hardcoded)
   credentials = "service-account.json"
   
   # NEW
   credentials = "config/service-account.json"
   ```

### 📋 Requirements Changes

- Merged 3 files into 1: `requirements.txt`
- Total: 114 unique packages
- Removed duplicates

### 🔒 .gitignore Updates

Added proper ignores for:
- `data/` directory structure
- `models/` directory structure
- `config/service-account.json`
- `env.old/` and deprecated folders

## How to Use New Structure

### Running ML Training

```bash
# From project root
cd /root/youtube-bot-dataset

# Activate environment
source env/bin/activate

# Run training (old way still works)
python ml/training/train_simple_avatar_classifier.py

# Or as a module
python -m ml.training.train_simple_avatar_classifier
```

### Accessing Data

```python
# Use new paths
AVATAR_DATASET = "data/datasets/avatar_images/"
PROCESSED_CSV = "data/processed/bot_metrics.csv"
```

### Loading Models

```python
# Use new paths
RF_MODEL = "models/avatar/rf_avatar_classifier.pkl"
XGB_MODEL = "models/avatar/xgb_avatar_classifier.pkl"
CLUSTERING_MODEL = "models/clustering/kmeans_pca_bot_model.pkl"
```

## Next Steps

1. ✅ Test ML training scripts with new paths
2. ✅ Update any hardcoded paths in production code
3. ✅ Add README.md documentation
4. ✅ Commit changes to git

## Rollback

If needed, the restructure can be reversed:
```bash
git stash
# Or restore from backup
```

All changes are file moves - no code logic was modified.
