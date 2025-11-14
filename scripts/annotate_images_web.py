#!/usr/bin/env python3
"""
Web-based Image Annotator for bot candidate avatars.

This allows you to review images in your browser and annotate them as:
- Bot: Move to train/bot/
- Human: Move to train/not_bot/
- Skip: Leave in candidates/

Works great on remote VMs without X11/GUI.

Usage:
    python scripts/annotate_images_web.py
    python scripts/annotate_images_web.py --port 8080 --source bot_candidates
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import List, Dict
import os

from flask import Flask, render_template_string, jsonify, send_file, request

app = Flask(__name__)

# Global state
IMAGES = []
CONFIG = {}
STATS = {
    'reviewed': 0,
    'moved_to_bot': 0,
    'moved_to_human': 0,
    'skipped': 0
}

# Paths
TRAIN_BOT_DIR = "data/datasets/avatar_images/train/bot"
TRAIN_HUMAN_DIR = "data/datasets/avatar_images/train/not_bot"


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Annotator - Bot Detection</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
            color: #333;
        }
        
        .header .stats {
            color: #666;
            font-size: 14px;
            margin-top: 15px;
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .stat-item {
            background: #f8f9fa;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 500;
        }
        
        .stat-item .number {
            color: #667eea;
            font-weight: 700;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 15px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
        }
        
        .main-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
            margin-bottom: 20px;
        }
        
        .image-container {
            position: relative;
            background: #f8f9fa;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 400px;
            padding: 20px;
        }
        
        .image-container img {
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .image-info {
            position: absolute;
            top: 15px;
            left: 15px;
            background: rgba(0, 0, 0, 0.75);
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .image-index {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(102, 126, 234, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 16px;
        }
        
        .details {
            padding: 25px;
        }
        
        .filename {
            font-size: 14px;
            color: #666;
            margin-bottom: 15px;
            word-break: break-all;
        }
        
        .probability {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 20px;
        }
        
        .prob-high { color: #dc3545; }
        .prob-medium { color: #fd7e14; }
        .prob-low { color: #28a745; }
        
        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
            padding: 25px;
            background: #f8f9fa;
        }
        
        .btn {
            flex: 1;
            max-width: 200px;
            padding: 15px 25px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn-bot {
            background: #dc3545;
            color: white;
        }
        
        .btn-bot:hover {
            background: #c82333;
        }
        
        .btn-human {
            background: #28a745;
            color: white;
        }
        
        .btn-human:hover {
            background: #218838;
        }
        
        .btn-skip {
            background: #6c757d;
            color: white;
        }
        
        .btn-skip:hover {
            background: #5a6268;
        }
        
        .keyboard-hints {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-top: 20px;
        }
        
        .keyboard-hints h3 {
            font-size: 16px;
            margin-bottom: 12px;
            color: #333;
        }
        
        .hints-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        
        .hint-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #666;
        }
        
        .key {
            background: #e9ecef;
            padding: 4px 10px;
            border-radius: 4px;
            font-family: monospace;
            font-weight: 600;
            font-size: 13px;
            color: #495057;
        }
        
        .complete-message {
            text-align: center;
            padding: 60px 20px;
        }
        
        .complete-message h2 {
            font-size: 32px;
            margin-bottom: 15px;
            color: #28a745;
        }
        
        .complete-message p {
            font-size: 16px;
            color: #666;
            margin-bottom: 25px;
        }
        
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin-top: 30px;
        }
        
        .summary-stat {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        
        .summary-stat .value {
            font-size: 28px;
            font-weight: 700;
            color: #667eea;
            display: block;
        }
        
        .summary-stat .label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .hidden {
            display: none !important;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid #e9ecef;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 15px;
        }
        
        @media (max-width: 768px) {
            .controls {
                flex-direction: column;
            }
            
            .btn {
                max-width: none;
            }
            
            .hints-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Bot Image Annotator</h1>
            <div class="stats">
                <div class="stat-item">
                    Total: <span class="number" id="totalCount">{{ total_images }}</span>
                </div>
                <div class="stat-item">
                    Reviewed: <span class="number" id="reviewedCount">0</span>
                </div>
                <div class="stat-item">
                    Bots: <span class="number" id="botCount">0</span>
                </div>
                <div class="stat-item">
                    Humans: <span class="number" id="humanCount">0</span>
                </div>
                <div class="stat-item">
                    Skipped: <span class="number" id="skipCount">0</span>
                </div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill" style="width: 0%"></div>
            </div>
        </div>
        
        <div id="annotationView" class="main-card">
            <div class="image-container">
                <div class="image-info" id="imageProb">Bot Probability: 0%</div>
                <div class="image-index" id="imageIndex">0 / {{ total_images }}</div>
                <img id="currentImage" src="" alt="Avatar">
            </div>
            
            <div class="details">
                <div class="filename" id="imageFilename">Loading...</div>
                <div class="probability" id="imageProbText">Bot Probability: 0%</div>
            </div>
            
            <div class="controls">
                <button class="btn btn-bot" onclick="annotate('bot')" id="btnBot">
                    🤖 <span>BOT</span>
                </button>
                <button class="btn btn-human" onclick="annotate('human')" id="btnHuman">
                    👤 <span>HUMAN</span>
                </button>
                <button class="btn btn-skip" onclick="annotate('skip')" id="btnSkip">
                    ⏭️ <span>SKIP</span>
                </button>
            </div>
        </div>
        
        <div id="completeView" class="main-card hidden">
            <div class="complete-message">
                <h2>🎉 All Done!</h2>
                <p>You've reviewed all available images.</p>
                
                <div class="summary-stats">
                    <div class="summary-stat">
                        <span class="value" id="finalReviewed">0</span>
                        <span class="label">Reviewed</span>
                    </div>
                    <div class="summary-stat">
                        <span class="value" id="finalBots">0</span>
                        <span class="label">Bots</span>
                    </div>
                    <div class="summary-stat">
                        <span class="value" id="finalHumans">0</span>
                        <span class="label">Humans</span>
                    </div>
                    <div class="summary-stat">
                        <span class="value" id="finalSkipped">0</span>
                        <span class="label">Skipped</span>
                    </div>
                </div>
                
                <button class="btn btn-skip" onclick="location.reload()" style="margin-top: 30px; max-width: 200px; margin-left: auto; margin-right: auto;">
                    🔄 Reload
                </button>
            </div>
        </div>
        
        <div class="keyboard-hints">
            <h3>⌨️ Keyboard Shortcuts</h3>
            <div class="hints-grid">
                <div class="hint-item">
                    <span class="key">B</span> → Mark as Bot
                </div>
                <div class="hint-item">
                    <span class="key">H</span> → Mark as Human
                </div>
                <div class="hint-item">
                    <span class="key">S</span> → Skip
                </div>
                <div class="hint-item">
                    <span class="key">←</span> → Previous
                </div>
                <div class="hint-item">
                    <span class="key">→</span> → Next (skip)
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentIndex = 0;
        let images = [];
        let stats = {
            reviewed: 0,
            moved_to_bot: 0,
            moved_to_human: 0,
            skipped: 0
        };
        
        // Load initial data
        async function init() {
            const response = await fetch('/api/images');
            const data = await response.json();
            images = data.images;
            
            if (images.length === 0) {
                showComplete();
            } else {
                loadImage(0);
            }
        }
        
        function loadImage(index) {
            if (index < 0 || index >= images.length) {
                showComplete();
                return;
            }
            
            currentIndex = index;
            const img = images[index];
            
            document.getElementById('currentImage').src = `/image/${img.original_index}`;
            document.getElementById('imageFilename').textContent = img.filename;
            
            const probPct = (img.bot_prob * 100).toFixed(1) + '%';
            const probClass = img.bot_prob >= 0.7 ? 'prob-high' : img.bot_prob >= 0.5 ? 'prob-medium' : 'prob-low';
            
            document.getElementById('imageProb').textContent = `Bot Probability: ${probPct}`;
            document.getElementById('imageProbText').textContent = `Bot Probability: ${probPct}`;
            document.getElementById('imageProbText').className = 'probability ' + probClass;
            
            document.getElementById('imageIndex').textContent = `${index + 1} / ${images.length}`;
            
            updateProgress();
        }
        
        async function annotate(action) {
            if (currentIndex >= images.length) return;
            
            const img = images[currentIndex];
            
            // Disable buttons during request
            disableButtons(true);
            
            try {
                const response = await fetch('/api/annotate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        index: img.original_index,
                        action: action
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Update stats
                    stats = result.stats;
                    updateStats();
                    
                    // Remove from list
                    images.splice(currentIndex, 1);
                    
                    // Load next image (stay at same index since we removed current)
                    if (images.length > 0) {
                        if (currentIndex >= images.length) {
                            currentIndex = images.length - 1;
                        }
                        loadImage(currentIndex);
                    } else {
                        showComplete();
                    }
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Failed to annotate: ' + error);
            } finally {
                disableButtons(false);
            }
        }
        
        function disableButtons(disabled) {
            document.getElementById('btnBot').disabled = disabled;
            document.getElementById('btnHuman').disabled = disabled;
            document.getElementById('btnSkip').disabled = disabled;
        }
        
        function updateStats() {
            document.getElementById('reviewedCount').textContent = stats.reviewed;
            document.getElementById('botCount').textContent = stats.moved_to_bot;
            document.getElementById('humanCount').textContent = stats.moved_to_human;
            document.getElementById('skipCount').textContent = stats.skipped;
        }
        
        function updateProgress() {
            const total = parseInt(document.getElementById('totalCount').textContent);
            const remaining = images.length;
            const reviewed = total - remaining;
            const progress = total > 0 ? (reviewed / total * 100) : 0;
            
            document.getElementById('progressFill').style.width = progress + '%';
        }
        
        function showComplete() {
            document.getElementById('annotationView').classList.add('hidden');
            document.getElementById('completeView').classList.remove('hidden');
            
            document.getElementById('finalReviewed').textContent = stats.reviewed;
            document.getElementById('finalBots').textContent = stats.moved_to_bot;
            document.getElementById('finalHumans').textContent = stats.moved_to_human;
            document.getElementById('finalSkipped').textContent = stats.skipped;
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (images.length === 0) return;
            
            const key = e.key.toLowerCase();
            
            if (key === 'b') {
                annotate('bot');
            } else if (key === 'h') {
                annotate('human');
            } else if (key === 's' || key === 'arrowright') {
                annotate('skip');
            } else if (key === 'arrowleft') {
                // Go back (skip backwards)
                if (currentIndex > 0) {
                    currentIndex--;
                    loadImage(currentIndex);
                }
            }
        });
        
        // Initialize on load
        init();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Main annotation page."""
    return render_template_string(HTML_TEMPLATE, total_images=len(IMAGES))


@app.route('/api/images')
def api_images():
    """Get list of images."""
    images_data = []
    for idx, img_info in enumerate(IMAGES):
        images_data.append({
            'original_index': idx,
            'filename': img_info['filename'],
            'bot_prob': img_info['bot_prob'],
            'path': img_info['path']
        })
    
    return jsonify({'images': images_data})


@app.route('/image/<int:index>')
def get_image(index):
    """Serve individual image."""
    if 0 <= index < len(IMAGES):
        img_path = IMAGES[index]['path']
        if Path(img_path).exists():
            return send_file(img_path, mimetype='image/jpeg')
    return "Image not found", 404


@app.route('/api/annotate', methods=['POST'])
def annotate():
    """Annotate an image and move it."""
    data = request.json
    index = data.get('index')
    action = data.get('action')
    
    if index is None or action not in ['bot', 'human', 'skip']:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    if index < 0 or index >= len(IMAGES):
        return jsonify({'success': False, 'error': 'Invalid index'}), 400
    
    img_info = IMAGES[index]
    source_path = Path(img_info['path'])
    
    try:
        if action == 'bot':
            # Move to train/bot
            dest_dir = Path(TRAIN_BOT_DIR)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / source_path.name
            shutil.move(str(source_path), str(dest_path))
            STATS['moved_to_bot'] += 1
            STATS['reviewed'] += 1
            
        elif action == 'human':
            # Move to train/not_bot
            dest_dir = Path(TRAIN_HUMAN_DIR)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / source_path.name
            shutil.move(str(source_path), str(dest_path))
            STATS['moved_to_human'] += 1
            STATS['reviewed'] += 1
            
        elif action == 'skip':
            # Just skip, don't move
            STATS['skipped'] += 1
        
        return jsonify({'success': True, 'stats': STATS})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get current stats."""
    return jsonify(STATS)


def load_images(source_dir: str, min_prob: float, max_prob: float):
    """Load images from directory."""
    source_path = Path(source_dir)
    
    # Convert to absolute path if relative
    if not source_path.is_absolute():
        source_path = source_path.resolve()
    
    if not source_path.exists():
        print(f"❌ Directory not found: {source_path}")
        return []
    
    patterns = ['*.jpg', '*.png', '*.jpeg', '*.JPG', '*.PNG']
    all_files = []
    for pattern in patterns:
        all_files.extend(source_path.glob(pattern))
    
    if not all_files:
        print(f"❌ No images found in {source_path}")
        return []
    
    images = []
    for path in all_files:
        # Extract bot probability
        try:
            prob_str = path.name.split('_')[-1].replace('.jpg', '').replace('.png', '')
            bot_prob = float(prob_str)
        except:
            bot_prob = 0.0
        
        # Filter by probability
        if not (min_prob <= bot_prob <= max_prob):
            continue
        
        images.append({
            'filename': path.name,
            'path': str(path),
            'bot_prob': bot_prob,
        })
    
    # Sort by probability (high to low) by default
    images.sort(key=lambda x: x['bot_prob'], reverse=True)
    
    return images


def main():
    parser = argparse.ArgumentParser(
        description="Web-based image annotator for bot detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start annotator
  python scripts/annotate_images_web.py
  
  # Custom port
  python scripts/annotate_images_web.py --port 8080
  
  # Different source directory
  python scripts/annotate_images_web.py --source train/bot
  
  # Filter by probability
  python scripts/annotate_images_web.py --min-prob 0.7
        """
    )
    
    parser.add_argument('--source', type=str, default='bot_candidates',
                       help='Source directory (relative to data/datasets/avatar_images/)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port to run web server on')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Host to bind to')
    parser.add_argument('--min-prob', type=float, default=0.0,
                       help='Minimum bot probability filter')
    parser.add_argument('--max-prob', type=float, default=1.0,
                       help='Maximum bot probability filter')
    
    args = parser.parse_args()
    
    # Resolve source directory
    if not args.source.startswith('/'):
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        source_dir = str(project_root / "data" / "datasets" / "avatar_images" / args.source)
    else:
        source_dir = args.source
    
    # Create output directories
    Path(TRAIN_BOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(TRAIN_HUMAN_DIR).mkdir(parents=True, exist_ok=True)
    
    # Load images
    global IMAGES, CONFIG
    IMAGES = load_images(source_dir, args.min_prob, args.max_prob)
    CONFIG = {
        'source_dir': source_dir,
        'min_prob': args.min_prob,
        'max_prob': args.max_prob
    }
    
    if not IMAGES:
        print("\n❌ No images found to annotate")
        return
    
    print("\n" + "="*70)
    print("🤖 Web-based Image Annotator")
    print("="*70)
    print(f"📁 Source: {source_dir}")
    print(f"🖼️  Images: {len(IMAGES)}")
    if args.min_prob > 0 or args.max_prob < 1:
        print(f"🔍 Filter: {args.min_prob:.2f} - {args.max_prob:.2f} probability")
    print(f"\n📂 Output folders:")
    print(f"   Bots → {TRAIN_BOT_DIR}")
    print(f"   Humans → {TRAIN_HUMAN_DIR}")
    print("="*70)
    print(f"\n🚀 Starting server on http://{args.host}:{args.port}")
    print(f"\n📝 Access the annotator:")
    print(f"   Local:  http://localhost:{args.port}")
    print(f"   Remote: http://<your-vm-ip>:{args.port}")
    print(f"\n💡 For SSH tunnel:")
    print(f"   ssh -L {args.port}:localhost:{args.port} user@server")
    print(f"   Then open: http://localhost:{args.port}")
    print(f"\n⌨️  Keyboard shortcuts:")
    print(f"   B → Mark as Bot")
    print(f"   H → Mark as Human")
    print(f"   S → Skip")
    print(f"\n🛑 Press Ctrl+C to stop\n")
    print("="*70)
    
    try:
        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
        print("\n📊 Final Stats:")
        print(f"   Reviewed: {STATS['reviewed']}")
        print(f"   Moved to bot: {STATS['moved_to_bot']}")
        print(f"   Moved to human: {STATS['moved_to_human']}")
        print(f"   Skipped: {STATS['skipped']}")


if __name__ == "__main__":
    main()
