# Quick Start: Google Search Bot Expansion

## TL;DR

Expand your bot channel graph by searching Google for related YouTube channels.

## Setup (One-Time)

1. **Get Google Custom Search credentials**:
   - Create CSE at https://programmablesearchengine.google.com/
   - Search site: `youtube.com`
   - Get API key from Google Cloud Console

2. **Set environment variables**:
   ```bash
   export GOOGLE_CSE_API_KEY="your-api-key"
   export GOOGLE_CSE_ID="your-search-engine-id"
   ```

## Usage

### Dry Run (Recommended First)

```bash
make expand-from-google-search-dry
```

This shows what channels would be discovered without actually expanding the graph.

### Run Expansion

```bash
# Default: 10 bot channels, min probability 0.7
make expand-from-google-search

# Custom parameters
make expand-from-google-search LIMIT=20 MIN_BOT_PROB=0.85
```

### Review Discovered Channels

```bash
make review
```

## Common Workflows

### Conservative Expansion

High confidence bots only:

```bash
make expand-from-google-search LIMIT=5 MIN_BOT_PROB=0.9
make review
```

### Aggressive Expansion

More channels, lower threshold:

```bash
make expand-from-google-search LIMIT=20 MIN_BOT_PROB=0.6 MAX_RESULTS=15
make capture-screenshots
make review
```

### Daily Quota-Aware Run

Stay within free tier (100 queries/day):

```bash
# ~3 queries per channel × 30 channels = ~90 queries
make expand-from-google-search LIMIT=30 MAX_RESULTS=10
```

## What Happens

1. ✅ Fetches top bot channels from Firestore
2. 🔍 Searches Google for related YouTube channels
3. ✅ Validates channels exist via YouTube API
4. 📸 Expands graph (screenshots, metadata, links)
5. 📝 Marks new channels as "pending_review"

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LIMIT` | 10 | Number of bot channels to process |
| `MIN_BOT_PROB` | 0.7 | Minimum bot probability (0.0-1.0) |
| `MAX_RESULTS` | 10 | Max search results per channel |
| `VALIDATE` | true | Validate channels exist |
| `DRY_RUN` | false | Preview without expanding |

## Troubleshooting

### "API credentials not configured"

Set the environment variables:

```bash
export GOOGLE_CSE_API_KEY="your-key"
export GOOGLE_CSE_ID="your-id"
```

### "No bot channels found"

Lower the threshold:

```bash
make expand-from-google-search MIN_BOT_PROB=0.5
```

### Quota Exceeded

Reduce the number of channels:

```bash
make expand-from-google-search LIMIT=5
```

## Full Documentation

See [GOOGLE_SEARCH_EXPANSION.md](GOOGLE_SEARCH_EXPANSION.md) for complete details.
