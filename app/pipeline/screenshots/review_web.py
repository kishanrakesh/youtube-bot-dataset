#!/usr/bin/env python3
"""Web-based manual review interface for channel screenshots.

Flask web application that allows annotating channels through a browser interface.
Replaces the OpenCV UI with a responsive web interface accessible remotely.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional

from flask import Flask, render_template, request, jsonify, session
from google.cloud import firestore, storage
from dotenv import load_dotenv
from datetime import timedelta

from app.pipeline.channels.scraping import expand_bot_graph_async

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

db = firestore.Client()
storage_client = storage.Client()
COLLECTION_NAME = "channel"


# ============================================================================
# Helper Functions
# ============================================================================

def get_signed_url(gcs_uri: str, expiration_minutes: int = 60) -> str:
    """Generate a signed URL for a GCS object.
    
    Args:
        gcs_uri: GCS URI (gs://bucket/path)
        expiration_minutes: URL expiration time in minutes
        
    Returns:
        Signed URL that can be accessed publicly
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return ""
    
    try:
        # Parse GCS URI
        uri_parts = gcs_uri[5:].split("/", 1)
        if len(uri_parts) != 2:
            return ""
        
        bucket_name, blob_name = uri_parts
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Generate signed URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        return url
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to generate signed URL for {gcs_uri}: {e}")
        return ""


# ============================================================================
# Data Fetching
# ============================================================================

def fetch_docs(limit: int = 200) -> List[dict]:
    """Fetch channel documents needing manual review.
    
    Queries for channels with screenshots but no bot labels yet,
    sorted by bot probability (highest first).
    
    Args:
        limit: Maximum number of documents to fetch
        
    Returns:
        List of channel document dictionaries
    """
    snaps = (
        db.collection(COLLECTION_NAME)
          .where("is_screenshot_stored", "==", True)
          .where("is_bot_checked", "==", False)
          .limit(limit)
          .stream()
    )

    docs = []
    for snap in snaps:
        doc = snap.to_dict()
        doc["id"] = snap.id
        
        # Use avatar_url (direct YouTube URL) for thumbnails
        # Convert screenshot GCS URIs to signed URLs for full view
        if doc.get("screenshot_gcs_uri"):
            doc["screenshot_url"] = get_signed_url(doc["screenshot_gcs_uri"])
        
        # avatar_url is already a public YouTube URL, no need to sign
        # But if avatar_gcs_uri exists, use that instead
        if doc.get("avatar_gcs_uri"):
            doc["avatar_display_url"] = get_signed_url(doc["avatar_gcs_uri"])
        elif doc.get("avatar_url"):
            doc["avatar_display_url"] = doc["avatar_url"]
        
        docs.append(doc)

    # Sort using avatar_metrics.bot_probability
    docs.sort(
        key=lambda d: d.get("avatar_metrics", {}).get("bot_probability", 0.0),
        reverse=True
    )

    LOGGER.info(f"Fetched {len(docs)} docs for manual review")
    return docs


# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def index():
    """Display the main review interface."""
    limit = int(request.args.get("limit", os.getenv("REVIEW_LIMIT", "200")))
    
    # Initialize session if needed
    if "reviewed_count" not in session:
        session["reviewed_count"] = 0
    
    docs = fetch_docs(limit=limit)
    
    return render_template(
        "review.html",
        docs=docs,
        total=len(docs),
        reviewed=session["reviewed_count"]
    )


@app.route("/api/docs")
def get_docs():
    """API endpoint to fetch documents for review."""
    limit = int(request.args.get("limit", 200))
    docs = fetch_docs(limit=limit)
    return jsonify({"docs": docs, "total": len(docs)})


@app.route("/api/label", methods=["POST"])
def label_channel():
    """API endpoint to label a channel as bot or not-bot.
    
    Expects JSON payload:
    {
        "channel_id": "UCxxx...",
        "is_bot": true/false
    }
    """
    data = request.json
    channel_id = data.get("channel_id")
    is_bot = data.get("is_bot")
    
    if not channel_id or is_bot is None:
        return jsonify({"error": "Missing channel_id or is_bot"}), 400
    
    try:
        now = datetime.now()
        doc_ref = db.collection(COLLECTION_NAME).document(channel_id)
        doc_ref.update({
            "is_bot": is_bot,
            "is_bot_check_type": "manual",
            "is_bot_checked": True,
            "is_bot_set_at": now,
            "last_checked_at": now,
        })
        
        # Update session count
        session["reviewed_count"] = session.get("reviewed_count", 0) + 1
        
        LOGGER.info(f"✅ Labeled {channel_id} as {'bot' if is_bot else 'not-bot'}")
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "is_bot": is_bot,
            "reviewed_count": session["reviewed_count"]
        })
    except Exception as e:
        LOGGER.error(f"❌ Error labeling {channel_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/label-bulk", methods=["POST"])
def label_bulk():
    """API endpoint to bulk label channels.
    
    Expects JSON payload:
    {
        "channel_ids": ["UCxxx...", "UCyyy..."],
        "is_bot": false
    }
    """
    data = request.json
    channel_ids = data.get("channel_ids", [])
    is_bot = data.get("is_bot", False)
    
    if not channel_ids:
        return jsonify({"error": "No channel IDs provided"}), 400
    
    try:
        now = datetime.now()
        batch = db.batch()
        
        for channel_id in channel_ids:
            doc_ref = db.collection(COLLECTION_NAME).document(channel_id)
            batch.update(doc_ref, {
                "is_bot": is_bot,
                "is_bot_check_type": "manual_bulk",
                "is_bot_checked": True,
                "is_bot_set_at": now,
                "last_checked_at": now,
            })
        
        batch.commit()
        
        # Update session count
        session["reviewed_count"] = session.get("reviewed_count", 0) + len(channel_ids)
        
        LOGGER.info(f"✅ Bulk labeled {len(channel_ids)} channels as {'bot' if is_bot else 'not-bot'}")
        return jsonify({
            "success": True,
            "labeled_count": len(channel_ids),
            "is_bot": is_bot,
            "reviewed_count": session["reviewed_count"]
        })
    except Exception as e:
        LOGGER.error(f"❌ Error bulk labeling: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/expand", methods=["POST"])
def expand_graph():
    """API endpoint to expand bot graph from labeled bot channels.
    
    Expects JSON payload:
    {
        "channel_ids": ["UCxxx...", "UCyyy..."]
    }
    """
    data = request.json
    channel_ids = data.get("channel_ids", [])
    
    if not channel_ids:
        return jsonify({"error": "No channel IDs provided"}), 400
    
    try:
        # Run expansion asynchronously
        asyncio.run(expand_bot_graph_async(channel_ids))
        
        LOGGER.info(f"🚀 Expanded bot graph from {len(channel_ids)} seeds")
        return jsonify({
            "success": True,
            "expanded_from": len(channel_ids)
        })
    except Exception as e:
        LOGGER.error(f"❌ Error expanding graph: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """Get review statistics."""
    try:
        total_channels = db.collection(COLLECTION_NAME).count().get()[0][0].value
        checked_channels = (
            db.collection(COLLECTION_NAME)
            .where("is_bot_checked", "==", True)
            .count()
            .get()[0][0].value
        )
        bot_channels = (
            db.collection(COLLECTION_NAME)
            .where("is_bot", "==", True)
            .count()
            .get()[0][0].value
        )
        
        return jsonify({
            "total_channels": total_channels,
            "checked_channels": checked_channels,
            "bot_channels": bot_channels,
            "pending_review": total_channels - checked_channels,
            "session_reviewed": session.get("reviewed_count", 0)
        })
    except Exception as e:
        LOGGER.error(f"❌ Error fetching stats: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Main
# ============================================================================

def main():
    """Launch the web review interface."""
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    LOGGER.info(f"🌐 Starting web review interface at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
