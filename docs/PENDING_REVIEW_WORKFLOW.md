# Pending Review Workflow

This document describes the new workflow for handling commenter channels discovered via the `register_commenters` pipeline, allowing them to be marked as pending review before manual classification as bots.

## Overview

Previously, all channels discovered through the bot graph expansion were immediately marked as `is_bot=True`. This caused a problem: when new channels were discovered via commenters, they would be marked as bots before manual review, potentially losing data if the channels were deleted or suspended.

The new workflow preserves full channel data (metadata, avatars, banners, screenshots, About page links) for newly discovered commenters WITHOUT marking them as confirmed bots, allowing manual review to make the final determination.

## Workflow Steps

### 1. Register Commenters
```bash
make register-commenters
```

This step:
- Extracts channel IDs from comment threads
- Filters by like threshold (default: 10 likes)
- Classifies avatars using XGBoost model
- Scrapes About pages for links and featured channels
- Stores basic channel data in Firestore
- **NEW**: Collects newly added channel IDs for expansion

### 2. Expand for Review (Automatic)
After registration completes, the system automatically expands discovered channels:

```python
await expand_channels_for_review(
    channel_ids=new_channels,
    use_api=True
)
```

This expansion:
- Sets `is_bot=False` for all discovered channels
- Sets `bot_check_type="pending_review"`
- Fetches full metadata via YouTube Data API
- Downloads and stores avatars to GCS
- Downloads and stores banners to GCS
- Captures screenshots of channel pages
- Scrapes About page for external links
- Recursively discovers featured channels and subscriptions
- **Preserves all data** even if channels are later deleted

### 3. Manual Review
Use the review UI to annotate channels:

```bash
make review
```

After annotation, the UI should update:
- `is_bot=True` for confirmed bots
- `bot_check_type="manual"` to indicate human verification

## Modified Files

### `app/pipeline/channels/scraping.py`
- **`_init_channel_doc()`**: Added `is_bot` and `bot_check_type` parameters with defaults
  - Default: `is_bot=True`, `bot_check_type="propagated"`
  
- **`expand_bot_graph_async()`**: Added `is_bot` and `bot_check_type` parameters
  - Passes these to all channel processing functions
  
- **`_process_channel_with_api()`**: Added `is_bot` and `bot_check_type` parameters
  - Propagates to channel document creation
  
- **`_process_channel_without_api()`**: Added `is_bot` and `bot_check_type` parameters
  - Propagates to channel document creation
  
- **`_process_subscriptions()`**: Added `is_bot` and `bot_check_type` parameters
  - Queues discovered channels for processing with parent's bot status

### `app/pipeline/comments/register_channels.py`
- **`expand_channels_for_review()`**: New function
  - Wrapper around `expand_bot_graph_async` with `is_bot=False`, `bot_check_type="pending_review"`
  
- **`register_commenter_channels()`**: Updated function
  - Added `expand_for_review` parameter (default: `True`)
  - Added `use_api_for_expansion` parameter (default: `True`)
  - Tracks newly added channel IDs in `new_channels` list
  - Calls `expand_channels_for_review()` after registration completes

## Channel Document Structure

Channels discovered for review have these fields:

```json
{
  "channel_id": "UC...",
  "is_bot": false,
  "is_bot_check_type": "pending_review",
  "is_bot_checked": false,
  "avatar_url": "https://...",
  "avatar_label": "HUMAN|BOT|DEFAULT|MISSING",
  "avatar_metrics": {
    "bot_probability": 0.75,
    "color_entropy": 3.2,
    "edge_density": 0.15,
    "skin_tone_fraction": 0.3
  },
  "about_links_count": 5,
  "featured_channels_count": 3,
  "is_screenshot_stored": true,
  "registered_at": "2024-01-15T10:30:00",
  "source": "register-commenters"
}
```

After manual review:
```json
{
  "is_bot": true,
  "is_bot_check_type": "manual",
  "is_bot_checked": true
}
```

## Backward Compatibility

The default parameter values ensure backward compatibility:
- Existing calls to `expand_bot_graph_async()` still work (defaults to `is_bot=True`)
- The `expand-channel` Makefile target still marks channels as bots by default
- Only `register_commenters` uses the new pending review workflow

## Usage Examples

### Expand specific channels for review (manual)
```bash
python -m app.pipeline.comments.register_channels --expand-only UC123... UC456...
```

### Disable automatic expansion (registration only)
```python
await register_commenter_channels(
    bucket="yt-bot-data",
    gcs_paths=["video_comments/raw/*.json"],
    expand_for_review=False  # Skip expansion
)
```

### Expand existing channels for review (backfill)
```python
from app.pipeline.comments.register_channels import expand_channels_for_review

# Get channels marked as is_bot_checked=False
db = firestore.Client()
docs = db.collection("channel").where("is_bot_checked", "==", False).stream()
channel_ids = [doc.id for doc in docs]

# Expand them for review
await expand_channels_for_review(channel_ids, use_api=True)
```

## Testing

1. Run register-commenters:
   ```bash
   make register-commenters
   ```

2. Check Firestore for new channels with:
   - `is_bot=False`
   - `bot_check_type="pending_review"`

3. Verify GCS storage:
   - Avatars in `gs://yt-bot-data/channel_avatars/`
   - Banners in `gs://yt-bot-data/channel_banners/`
   - Screenshots in `gs://yt-bot-data/screenshots/`

4. Run review UI:
   ```bash
   make review
   ```

5. After annotation, verify channels updated to:
   - `is_bot=True`
   - `bot_check_type="manual"`

## Future Improvements

- [ ] Add CLI flag to `register.py` for `--expand-for-review` / `--no-expand`
- [ ] Update review UI to batch-update `is_bot` status
- [ ] Add metrics tracking for pending review queue size
- [ ] Create separate collection for pending channels to improve query performance
- [ ] Add scheduled job to re-check channels that are still pending after X days
