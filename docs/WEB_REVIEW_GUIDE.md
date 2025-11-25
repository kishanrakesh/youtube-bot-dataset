# Web Review Interface Guide

## Overview

The web review interface provides a browser-based alternative to the OpenCV UI for manually annotating channels as bots or not-bots. This allows you to review channels from any device with a web browser, including remote access.

## Features

- 📊 **Grid View**: Browse multiple channel screenshots at once
- 🔍 **Full Screenshot**: Click any screenshot to view it full-size
- ⌨️ **Keyboard Shortcuts**: Fast labeling with B (bot) and N (not-bot) keys
- 📈 **Real-time Stats**: Track your progress and remaining channels
- 🚀 **Bot Graph Expansion**: Automatically discover related channels from labeled bots
- 💾 **Auto-save**: Labels are saved immediately to Firestore

## Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements-web.txt
```

### 2. Set Environment Variables

Create or update your `.env` file:

```bash
# Required
GCS_BUCKET_DATA=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=config/service-account.json

# Optional
FLASK_SECRET_KEY=your-secret-key-here
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
REVIEW_LIMIT=200
```

### 3. Run the Web Server

```bash
python -m app.pipeline.screenshots.review_web
```

Or use the provided script:

```bash
# Local access only
python3 app/pipeline/screenshots/review_web.py

# Remote access (accessible from other devices on your network)
FLASK_HOST=0.0.0.0 python3 app/pipeline/screenshots/review_web.py
```

### 4. Access the Interface

Open your browser and navigate to:
- Local: `http://localhost:5000`
- Remote: `http://YOUR_SERVER_IP:5000`

## Usage

### Reviewing Channels

1. **Browse Grid**: Scroll through the grid of channel screenshots
2. **View Details**: Click any screenshot to see it full-size
3. **Label**:
   - Click "🤖 Bot" button or press `B` to mark as bot
   - Click "✅ Not Bot" button or press `N` to mark as not-bot
4. **Navigate**: Press `ESC` to close the full-size view

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `B` | Mark current channel as bot (in modal view) |
| `N` | Mark current channel as not-bot (in modal view) |
| `ESC` | Close full-size screenshot modal |

### Bot Graph Expansion

After labeling several channels as bots:

1. Click the "🚀 Expand Bot Graph" button
2. Confirm the expansion
3. The system will:
   - Scrape featured channels and subscriptions
   - Download screenshots and metadata
   - Add new channels to the review queue

## Metrics Explained

Each channel card shows avatar metrics if available:

- **Bot Prob**: Predicted bot probability (0-100%)
  - 🔴 Red (>70%): High probability
  - 🟡 Orange (40-70%): Medium probability
  - 🟢 Green (<40%): Low probability
- **Entropy**: Image randomness/complexity
- **Edges**: Edge density percentage
- **Hue Std**: Color variation (standard deviation of hue)

## API Endpoints

The web interface exposes several API endpoints:

### Get Documents
```bash
GET /api/docs?limit=200
```

### Label Channel
```bash
POST /api/label
Content-Type: application/json

{
  "channel_id": "UCxxx...",
  "is_bot": true
}
```

### Expand Bot Graph
```bash
POST /api/expand
Content-Type: application/json

{
  "channel_ids": ["UCxxx...", "UCyyy..."]
}
```

### Get Statistics
```bash
GET /api/stats
```

## Deployment

### Local Development
```bash
FLASK_DEBUG=True python3 app/pipeline/screenshots/review_web.py
```

### Production (Using Gunicorn)

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run the server:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app.pipeline.screenshots.review_web:app
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install -r requirements.txt -r requirements-web.txt

COPY . .

ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8080

CMD ["python", "-m", "app.pipeline.screenshots.review_web"]
```

Build and run:
```bash
docker build -t channel-review .
docker run -p 8080:8080 -v $(pwd)/config:/app/config channel-review
```

### Cloud Run Deployment

```bash
gcloud run deploy channel-review \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FLASK_HOST=0.0.0.0,FLASK_PORT=8080
```

## Troubleshooting

### Images Not Loading

If screenshots don't load:
1. Check GCS bucket permissions (make objects publicly readable or use signed URLs)
2. Verify the `screenshot_gcs_uri` field exists in Firestore documents
3. Check browser console for CORS errors

### Session Data Lost

If reviewed count resets:
1. Set a persistent `FLASK_SECRET_KEY` in your `.env`
2. Use a production-grade session backend (Redis, database)

### Performance Issues

For better performance with large datasets:
1. Reduce `REVIEW_LIMIT` to load fewer channels
2. Enable pagination in the interface
3. Use caching for repeated queries
4. Deploy with multiple workers (Gunicorn)

## Comparison: Web vs OpenCV UI

| Feature | Web UI | OpenCV UI |
|---------|--------|-----------|
| Remote Access | ✅ Yes | ❌ No |
| Multi-device | ✅ Yes | ❌ No |
| Setup Complexity | Simple | Requires X11/display |
| Performance | Good | Excellent |
| Keyboard Shortcuts | Limited | Full |
| Batch Operations | ✅ Yes | ❌ No |
| Graph Expansion | ✅ Integrated | ⚠️ Separate script |

## Future Enhancements

- [ ] Pagination for large datasets
- [ ] Bulk labeling operations
- [ ] Undo/redo functionality
- [ ] Search and filter channels
- [ ] Export labels to CSV/JSON
- [ ] Multi-user support with authentication
- [ ] Real-time collaboration
- [ ] Advanced keyboard navigation

## Support

For issues or questions, check:
- Project README: `docs/README.md`
- Firestore schema: Run `python scripts/check_firestore_schema.py`
- Logs: Check application logs for errors
