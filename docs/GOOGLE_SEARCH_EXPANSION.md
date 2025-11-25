# Bot Graph Expansion via Google Custom Search

This guide explains how to use the Google Custom Search integration to discover and expand the bot channel graph.

## Overview

The `expand_from_google_search.py` pipeline automates the process of:

1. **Fetching confirmed bot channels** from Firestore based on bot probability
2. **Searching Google Custom Search** for related YouTube channels (using `youtube.com/@` and `youtube.com/channel/` filters)
3. **Validating discovered channels** to ensure they still exist on YouTube
4. **Expanding the bot graph** for each valid channel
5. **Marking channels as `pending_review`** until manual review confirms bot status

## Prerequisites

### 1. Google Custom Search API Setup

You need to set up Google Custom Search API credentials:

1. **Create a Custom Search Engine (CSE)**:
   - Go to [Google Custom Search](https://programmablesearchengine.google.com/)
   - Click "Add" to create a new search engine
   - In "Sites to search", enter: `youtube.com`
   - Name it something like "YouTube Channel Search"
   - Click "Create"
   - Note your **Search Engine ID** (looks like: `0123456789abcdef:a1b2c3d4e5`)

2. **Get API Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the "Custom Search API"
   - Go to "Credentials" → "Create Credentials" → "API Key"
   - Note your **API Key**

3. **Set Environment Variables**:
   ```bash
   export GOOGLE_CSE_API_KEY="your-api-key-here"
   export GOOGLE_CSE_ID="your-search-engine-id-here"
   ```

   Or add to your `.env` file:
   ```
   GOOGLE_CSE_API_KEY=your-api-key-here
   GOOGLE_CSE_ID=your-search-engine-id-here
   ```

### 2. Firestore Collections

The pipeline uses the following Firestore collections:

- `channel` - Main channel collection with bot status
- `channel_pending` - Channels awaiting resolution (handles)
- `channel_discoveries` - Metadata about how channels were discovered
- `channel_links` - Graph edges between channels

## Usage

### Basic Usage

Run a dry-run first to see what channels would be discovered:

```bash
make expand-from-google-search-dry
```

Run the actual expansion:

```bash
make expand-from-google-search
```

### Advanced Options

Customize the expansion parameters:

```bash
# Process top 20 bot channels with bot probability >= 0.8
make expand-from-google-search LIMIT=20 MIN_BOT_PROB=0.8

# Get up to 20 search results per bot channel
make expand-from-google-search MAX_RESULTS=20

# Disable channel validation (faster but may include deleted channels)
make expand-from-google-search VALIDATE=false

# Disable YouTube API (use scraping only)
make expand-from-google-search EXPAND_USE_API=false
```

### Direct Python Invocation

You can also run the script directly:

```bash
# Basic usage
python -m app.pipeline.channels.expand_from_google_search

# With options
python -m app.pipeline.channels.expand_from_google_search \
  --limit 10 \
  --min-bot-probability 0.7 \
  --max-results-per-channel 10 \
  --use-api \
  --validate \
  --dry-run

# See all options
python -m app.pipeline.channels.expand_from_google_search --help
```

## How It Works

### 1. Fetch Bot Channels

The pipeline queries Firestore for channels matching:
- `is_bot == True`
- `is_bot_checked == True` (manually reviewed)
- `avatar_metrics.bot_probability >= min_bot_probability`

Channels are sorted by bot probability (highest first).

### 2. Google Custom Search

For each bot channel, the pipeline performs multiple search queries:

```
site:youtube.com/channel OR site:youtube.com/@ {channel_id}
site:youtube.com/channel OR site:youtube.com/@ "{channel_title}"
site:youtube.com related channels {channel_id}
```

This searches for:
- Channels directly linked to the bot channel
- Channels with similar names
- Channels suggested as related

### 3. Extract Channel Identifiers

From the search results, the pipeline extracts:
- Channel IDs (format: `UC...`)
- Channel handles (format: `@username`)

Using regex patterns:
- `youtube.com/channel/(UC[a-zA-Z0-9_-]+)`
- `youtube.com/@([a-zA-Z0-9_.-]+)`

### 4. Validate Channels

If `--validate` is enabled (default), the pipeline checks each discovered channel using the YouTube Data API to ensure:
- The channel still exists
- The channel is accessible
- We can fetch metadata

### 5. Expand Bot Graph

For each validated channel, the pipeline calls `expand_bot_graph_async()` with:
- `is_bot=False` - Mark as non-bot initially
- `bot_check_type="pending_review"` - Requires manual review

This performs the full expansion:
- Fetch channel metadata via YouTube API
- Scrape About page for external links
- Scrape featured channels and subscriptions
- Capture screenshots
- Store all data to Firestore and GCS

### 6. Track Discoveries

Each discovery is logged to the `channel_discoveries` collection:

```python
{
  "discovered_from_channel_id": "UC...",  # Source bot channel
  "discovered_channel_id": "UC...",       # Newly found channel
  "discovery_method": "google_custom_search",
  "discovered_at": timestamp,
  "is_validated": True/False
}
```

## Output and Results

### Console Output

The pipeline provides detailed logging:

```
📥 Fetching bot channels (min_probability=0.7, is_bot_checked=True)...
✅ Found 10 bot channels

================================================================================
[1/10] Processing bot channel: UCxxx...
   Title: Example Bot Channel
   Bot Probability: 0.9234
================================================================================
🔍 Searching: site:youtube.com/channel OR site:youtube.com/@ UCxxx...
🔍 Found 8 results for query: ...
   Found 8 potential channels
✅ Channel @example exists: UCyyy...
   Validated 6 channels
   🚀 Expanding graph for 6 channels...
   ✅ Expansion complete for 6 channels

📊 Expansion Summary
================================================================================
Bot channels processed: 10
Total channels discovered: 127
Total channels validated: 98
Total channels expanded: 98
================================================================================
```

### Firestore Data

After expansion, you'll have:

1. **New channel documents** in the `channel` collection with:
   - `is_bot = False`
   - `is_bot_check_type = "pending_review"`
   - `is_bot_checked = False`

2. **Discovery metadata** in the `channel_discoveries` collection

3. **Graph edges** in the `channel_links` collection

### Manual Review

After expansion, review the discovered channels:

```bash
# View channels pending review
python -m scripts.list_channels --filter pending_review

# Launch review UI
make review
```

Mark channels as bots or non-bots through the review UI.

## Configuration Options

### Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--limit` | int | 10 | Maximum number of bot channels to process |
| `--min-bot-probability` | float | 0.7 | Minimum bot probability threshold (0.0-1.0) |
| `--max-results-per-channel` | int | 10 | Maximum Google search results per bot channel |
| `--use-api` / `--no-use-api` | bool | True | Use YouTube Data API for validation and expansion |
| `--validate` / `--no-validate` | bool | True | Validate channels exist before expanding |
| `--dry-run` | bool | False | Don't actually expand, just report findings |

### Makefile Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIMIT` | 10 | Number of bot channels to process |
| `MIN_BOT_PROB` | 0.7 | Minimum bot probability |
| `MAX_RESULTS` | 10 | Max results per channel |
| `VALIDATE` | true | Enable channel validation |
| `DRY_RUN` | false | Enable dry-run mode |
| `EXPAND_USE_API` | true | Use YouTube API |

## Best Practices

### 1. Start with Dry Run

Always run a dry-run first to see what would be discovered:

```bash
make expand-from-google-search-dry
```

### 2. Use High Bot Probability Threshold

Start with high-confidence bots to avoid false positives:

```bash
make expand-from-google-search MIN_BOT_PROB=0.85
```

### 3. Incremental Expansion

Process a small number of channels at a time:

```bash
# Process 5 channels at a time
make expand-from-google-search LIMIT=5
```

### 4. Review Regularly

After each expansion run, review the discovered channels:

```bash
make review
```

### 5. Monitor API Quotas

Google Custom Search has daily quotas:
- **Free tier**: 100 queries/day
- **Paid tier**: Up to 10,000 queries/day

Each bot channel uses multiple queries (usually 2-3), so plan accordingly:
- Free tier: ~30 bot channels/day
- With 10 results per channel: ~3 queries × 30 = ~90 queries/day

## Troubleshooting

### Error: "Google Custom Search API credentials not configured"

Make sure you've set the environment variables:

```bash
export GOOGLE_CSE_API_KEY="your-api-key"
export GOOGLE_CSE_ID="your-search-engine-id"
```

### Error: "No bot channels found matching criteria"

Lower the bot probability threshold:

```bash
make expand-from-google-search MIN_BOT_PROB=0.5
```

Or check that you have confirmed bot channels in Firestore.

### Search Returns No Results

Try adjusting the search patterns in the code, or check that your Custom Search Engine is configured to search `youtube.com`.

### API Quota Exceeded

If you hit the Google Custom Search quota:
- Reduce `LIMIT` (number of bot channels)
- Reduce `MAX_RESULTS` (results per channel)
- Wait until quota resets (midnight Pacific Time)
- Consider upgrading to paid tier

## Examples

### Example 1: Conservative Expansion

High confidence, thorough validation:

```bash
make expand-from-google-search \
  LIMIT=5 \
  MIN_BOT_PROB=0.9 \
  MAX_RESULTS=5 \
  VALIDATE=true
```

### Example 2: Aggressive Expansion

More channels, lower threshold:

```bash
make expand-from-google-search \
  LIMIT=20 \
  MIN_BOT_PROB=0.6 \
  MAX_RESULTS=15 \
  VALIDATE=true
```

### Example 3: Fast Scraping Mode

No API validation (faster but less reliable):

```bash
make expand-from-google-search \
  LIMIT=10 \
  VALIDATE=false \
  EXPAND_USE_API=false
```

## Integration with Existing Workflows

The expansion pipeline integrates seamlessly with existing workflows:

```bash
# 1. Expand from Google Search
make expand-from-google-search LIMIT=10

# 2. Review discovered channels
make review

# 3. Capture screenshots for newly confirmed bots
make capture-screenshots

# 4. Repeat
```

Or create a combined workflow in the Makefile:

```makefile
.PHONY: expand-and-review
expand-and-review:
	make expand-from-google-search
	make capture-screenshots
	make review
```

## See Also

- [expand_single.py](../app/pipeline/channels/expand_single.py) - Expand individual channels
- [scraping.py](../app/pipeline/channels/scraping.py) - Core expansion logic
- [Makefile](../Makefile) - All available commands
