#!/usr/bin/env python3
"""
Web-based Image Viewer for reviewing scraped avatar images.

This viewer runs a local web server that you can access through your browser,
making it perfect for remote VMs and SSH sessions.

Usage:
    # Start the web viewer
    python scripts/review_images_web.py
    
    # Custom port and source
    python scripts/review_images_web.py --port 8080 --source bot_candidates
    
    # Filter by probability
    python scripts/review_images_web.py --min-prob 0.7
    
Then open in your browser:
    http://localhost:5000
    
Or if accessing remotely via SSH tunnel:
    ssh -L 5000:localhost:5000 user@server
    Then open: http://localhost:5000
"""

import argparse
import base64
import json
import os
from pathlib import Path
from typing import List, Dict
import io

from flask import Flask, render_template_string, jsonify, send_file
import cv2
import numpy as np

app = Flask(__name__)

# Global state
IMAGES = []
CONFIG = {}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Viewer - {{ config.source_dir }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 24px;
            margin-bottom: 10px;
            color: #333;
        }
        
        .header .stats {
            color: #666;
            font-size: 14px;
        }
        
        .controls {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .controls label {
            font-weight: 500;
            color: #333;
        }
        
        .controls select, .controls input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        
        .controls button {
            padding: 8px 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }
        
        .controls button:hover {
            background: #0056b3;
        }
        
        .view-modes {
            display: flex;
            gap: 10px;
        }
        
        .view-mode-btn {
            padding: 8px 16px;
            background: #e9ecef;
            color: #495057;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .view-mode-btn.active {
            background: #007bff;
            color: white;
        }
        
        .view-mode-btn:hover {
            background: #dee2e6;
        }
        
        .view-mode-btn.active:hover {
            background: #0056b3;
        }
        
        /* Grid View */
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .image-card {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }
        
        .image-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .image-card img {
            width: 100%;
            height: 200px;
            object-fit: cover;
            display: block;
        }
        
        .image-card .info {
            padding: 10px;
        }
        
        .image-card .filename {
            font-size: 12px;
            color: #666;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-bottom: 5px;
        }
        
        .image-card .probability {
            font-size: 14px;
            font-weight: 600;
        }
        
        .prob-high { color: #dc3545; }
        .prob-medium { color: #fd7e14; }
        .prob-low { color: #28a745; }
        
        /* List View */
        .list-container {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .list-item {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            gap: 15px;
            align-items: center;
            cursor: pointer;
            transition: box-shadow 0.2s;
        }
        
        .list-item:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .list-item img {
            width: 100px;
            height: 100px;
            object-fit: cover;
            border-radius: 4px;
        }
        
        .list-item .details {
            flex: 1;
        }
        
        .list-item .index {
            font-size: 18px;
            font-weight: 600;
            color: #999;
            min-width: 60px;
        }
        
        /* Detail Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            padding: 20px;
        }
        
        .modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .modal-content {
            background: white;
            border-radius: 8px;
            max-width: 90%;
            max-height: 90%;
            overflow: auto;
            position: relative;
        }
        
        .modal-header {
            padding: 20px;
            border-bottom: 1px solid #dee2e6;
            position: sticky;
            top: 0;
            background: white;
            z-index: 1;
        }
        
        .modal-close {
            position: absolute;
            top: 15px;
            right: 15px;
            font-size: 28px;
            cursor: pointer;
            color: #666;
            background: none;
            border: none;
            padding: 0 10px;
        }
        
        .modal-close:hover {
            color: #000;
        }
        
        .modal-body {
            padding: 20px;
            text-align: center;
        }
        
        .modal-body img {
            max-width: 100%;
            max-height: 70vh;
            border-radius: 4px;
        }
        
        .modal-info {
            margin-top: 20px;
            text-align: left;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .modal-info p {
            margin: 8px 0;
            font-size: 14px;
            color: #495057;
        }
        
        .modal-nav {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
            padding: 0 20px 20px;
        }
        
        .modal-nav button {
            padding: 10px 20px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .modal-nav button:hover {
            background: #0056b3;
        }
        
        .modal-nav button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .pagination button {
            padding: 8px 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .pagination button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .pagination span {
            color: #666;
            font-size: 14px;
        }
        
        .hidden {
            display: none !important;
        }
        
        @media (max-width: 768px) {
            .grid-container {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }
            
            .controls {
                flex-direction: column;
                align-items: stretch;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🖼️ Image Viewer</h1>
        <div class="stats">
            <strong>{{ images|length }}</strong> images from <strong>{{ config.source_dir }}</strong>
            {% if config.min_prob > 0 or config.max_prob < 1 %}
            | Filtered: {{ config.min_prob }}–{{ config.max_prob }} probability
            {% endif %}
        </div>
    </div>
    
    <div class="controls">
        <div class="view-modes">
            <button class="view-mode-btn active" onclick="setViewMode('grid')">Grid</button>
            <button class="view-mode-btn" onclick="setViewMode('list')">List</button>
        </div>
        
        <label>
            Sort:
            <select id="sortSelect" onchange="sortImages()">
                <option value="prob-desc">Probability (High→Low)</option>
                <option value="prob-asc">Probability (Low→High)</option>
                <option value="name">Filename</option>
                <option value="index">Original Order</option>
            </select>
        </label>
        
        <label>
            Per page:
            <select id="perPageSelect" onchange="changePerPage()">
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="all">All</option>
            </select>
        </label>
        
        <button onclick="location.reload()">🔄 Refresh</button>
    </div>
    
    <div id="gridView" class="grid-container"></div>
    <div id="listView" class="list-container hidden"></div>
    
    <div class="pagination">
        <button onclick="previousPage()" id="prevBtn">← Previous</button>
        <span id="pageInfo">Page 1</span>
        <button onclick="nextPage()" id="nextBtn">Next →</button>
    </div>
    
    <div id="modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalTitle">Image Details</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <img id="modalImage" src="" alt="">
                <div class="modal-info">
                    <p><strong>Index:</strong> <span id="modalIndex"></span></p>
                    <p><strong>Filename:</strong> <span id="modalFilename"></span></p>
                    <p><strong>Bot Probability:</strong> <span id="modalProb"></span></p>
                    <p><strong>Dimensions:</strong> <span id="modalDims"></span></p>
                    <p><strong>Path:</strong> <span id="modalPath"></span></p>
                </div>
            </div>
            <div class="modal-nav">
                <button onclick="previousImage()" id="modalPrevBtn">← Previous</button>
                <button onclick="nextImage()" id="modalNextBtn">Next →</button>
            </div>
        </div>
    </div>
    
    <script>
        let allImages = {{ images_json|safe }};
        let displayImages = [...allImages];
        let currentPage = 1;
        let perPage = 20;
        let viewMode = 'grid';
        let currentModalIndex = -1;
        
        function setViewMode(mode) {
            viewMode = mode;
            document.querySelectorAll('.view-mode-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            if (mode === 'grid') {
                document.getElementById('gridView').classList.remove('hidden');
                document.getElementById('listView').classList.add('hidden');
            } else {
                document.getElementById('gridView').classList.add('hidden');
                document.getElementById('listView').classList.remove('hidden');
            }
            
            renderImages();
        }
        
        function sortImages() {
            const sortBy = document.getElementById('sortSelect').value;
            
            if (sortBy === 'prob-desc') {
                displayImages.sort((a, b) => b.bot_prob - a.bot_prob);
            } else if (sortBy === 'prob-asc') {
                displayImages.sort((a, b) => a.bot_prob - b.bot_prob);
            } else if (sortBy === 'name') {
                displayImages.sort((a, b) => a.filename.localeCompare(b.filename));
            } else if (sortBy === 'index') {
                displayImages.sort((a, b) => a.original_index - b.original_index);
            }
            
            currentPage = 1;
            renderImages();
        }
        
        function changePerPage() {
            const value = document.getElementById('perPageSelect').value;
            perPage = value === 'all' ? displayImages.length : parseInt(value);
            currentPage = 1;
            renderImages();
        }
        
        function getProbClass(prob) {
            if (prob >= 0.7) return 'prob-high';
            if (prob >= 0.5) return 'prob-medium';
            return 'prob-low';
        }
        
        function renderImages() {
            const start = (currentPage - 1) * perPage;
            const end = Math.min(start + perPage, displayImages.length);
            const pageImages = displayImages.slice(start, end);
            
            if (viewMode === 'grid') {
                renderGridView(pageImages);
            } else {
                renderListView(pageImages);
            }
            
            updatePagination();
        }
        
        function renderGridView(images) {
            const container = document.getElementById('gridView');
            container.innerHTML = images.map((img, idx) => `
                <div class="image-card" onclick="openModal(${(currentPage - 1) * perPage + idx})">
                    <img src="/image/${img.original_index}" alt="${img.filename}">
                    <div class="info">
                        <div class="filename" title="${img.filename}">${img.filename}</div>
                        <div class="probability ${getProbClass(img.bot_prob)}">
                            ${(img.bot_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        function renderListView(images) {
            const container = document.getElementById('listView');
            container.innerHTML = images.map((img, idx) => `
                <div class="list-item" onclick="openModal(${(currentPage - 1) * perPage + idx})">
                    <div class="index">#${img.original_index + 1}</div>
                    <img src="/image/${img.original_index}" alt="${img.filename}">
                    <div class="details">
                        <div style="font-weight: 600; margin-bottom: 5px;">${img.filename}</div>
                        <div class="probability ${getProbClass(img.bot_prob)}">
                            Bot Probability: ${(img.bot_prob * 100).toFixed(1)}%
                        </div>
                        <div style="font-size: 12px; color: #666; margin-top: 5px;">
                            ${img.width} × ${img.height} px
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        function updatePagination() {
            const totalPages = Math.ceil(displayImages.length / perPage);
            const start = (currentPage - 1) * perPage + 1;
            const end = Math.min(currentPage * perPage, displayImages.length);
            
            document.getElementById('pageInfo').textContent = 
                `Page ${currentPage} of ${totalPages} | Showing ${start}-${end} of ${displayImages.length}`;
            document.getElementById('prevBtn').disabled = currentPage === 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages;
        }
        
        function previousPage() {
            if (currentPage > 1) {
                currentPage--;
                renderImages();
                window.scrollTo(0, 0);
            }
        }
        
        function nextPage() {
            const totalPages = Math.ceil(displayImages.length / perPage);
            if (currentPage < totalPages) {
                currentPage++;
                renderImages();
                window.scrollTo(0, 0);
            }
        }
        
        function openModal(index) {
            const img = displayImages[index];
            currentModalIndex = index;
            
            document.getElementById('modalImage').src = `/image/${img.original_index}`;
            document.getElementById('modalIndex').textContent = `${img.original_index + 1} of ${allImages.length}`;
            document.getElementById('modalFilename').textContent = img.filename;
            document.getElementById('modalProb').innerHTML = 
                `<span class="${getProbClass(img.bot_prob)}">${(img.bot_prob * 100).toFixed(2)}%</span>`;
            document.getElementById('modalDims').textContent = `${img.width} × ${img.height} px`;
            document.getElementById('modalPath').textContent = img.path;
            
            document.getElementById('modal').classList.add('active');
            document.getElementById('modalPrevBtn').disabled = index === 0;
            document.getElementById('modalNextBtn').disabled = index === displayImages.length - 1;
            
            // Keyboard navigation
            document.addEventListener('keydown', handleModalKeyboard);
        }
        
        function closeModal() {
            document.getElementById('modal').classList.remove('active');
            document.removeEventListener('keydown', handleModalKeyboard);
        }
        
        function previousImage() {
            if (currentModalIndex > 0) {
                openModal(currentModalIndex - 1);
            }
        }
        
        function nextImage() {
            if (currentModalIndex < displayImages.length - 1) {
                openModal(currentModalIndex + 1);
            }
        }
        
        function handleModalKeyboard(e) {
            if (e.key === 'Escape') closeModal();
            else if (e.key === 'ArrowLeft') previousImage();
            else if (e.key === 'ArrowRight') nextImage();
        }
        
        // Click outside modal to close
        document.getElementById('modal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
        
        // Initial render
        renderImages();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Main page with image grid."""
    images_data = []
    for idx, img_info in enumerate(IMAGES):
        images_data.append({
            'original_index': idx,
            'filename': img_info['filename'],
            'bot_prob': img_info['bot_prob'],
            'width': img_info['width'],
            'height': img_info['height'],
            'path': img_info['path']
        })
    
    return render_template_string(
        HTML_TEMPLATE,
        images=IMAGES,
        images_json=json.dumps(images_data),
        config=CONFIG
    )


@app.route('/image/<int:index>')
def get_image(index):
    """Serve individual image."""
    if 0 <= index < len(IMAGES):
        img_path = IMAGES[index]['path']
        return send_file(img_path, mimetype='image/jpeg')
    return "Image not found", 404


@app.route('/api/images')
def api_images():
    """API endpoint for image list."""
    return jsonify(IMAGES)


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
        
        # Get image dimensions
        try:
            img = cv2.imread(str(path))
            if img is not None:
                height, width = img.shape[:2]
            else:
                width, height = 0, 0
        except:
            width, height = 0, 0
        
        images.append({
            'filename': path.name,
            'path': str(path),
            'bot_prob': bot_prob,
            'width': width,
            'height': height
        })
    
    # Sort by probability (high to low) by default
    images.sort(key=lambda x: x['bot_prob'], reverse=True)
    
    return images


def main():
    parser = argparse.ArgumentParser(
        description="Web-based image viewer for scraped avatars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start viewer on default port
  python scripts/review_images_web.py
  
  # Custom port
  python scripts/review_images_web.py --port 8080
  
  # View specific directory
  python scripts/review_images_web.py --source train/bot
  
  # Filter by probability
  python scripts/review_images_web.py --min-prob 0.7
  
  # SSH tunnel for remote access
  ssh -L 5000:localhost:5000 user@server
  # Then open http://localhost:5000 in your local browser
        """
    )
    
    parser.add_argument('--source', type=str, default='bot_candidates',
                       help='Source directory (relative to data/datasets/avatar_images/ or absolute)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port to run web server on')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Host to bind to (0.0.0.0 for all interfaces)')
    parser.add_argument('--min-prob', type=float, default=0.0,
                       help='Minimum bot probability filter')
    parser.add_argument('--max-prob', type=float, default=1.0,
                       help='Maximum bot probability filter')
    
    args = parser.parse_args()
    
    # Resolve source directory - use absolute path
    if not args.source.startswith('/'):
        # Get the project root (parent of scripts directory)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        source_dir = str(project_root / "data" / "datasets" / "avatar_images" / args.source)
    else:
        source_dir = args.source
    
    # Load images
    global IMAGES, CONFIG
    IMAGES = load_images(source_dir, args.min_prob, args.max_prob)
    CONFIG = {
        'source_dir': source_dir,
        'min_prob': args.min_prob,
        'max_prob': args.max_prob
    }
    
    if not IMAGES:
        print("\n❌ No images found to display")
        return
    
    print("\n" + "="*70)
    print("🌐 Web-based Image Viewer")
    print("="*70)
    print(f"📁 Source: {source_dir}")
    print(f"🖼️  Images: {len(IMAGES)}")
    if args.min_prob > 0 or args.max_prob < 1:
        print(f"🔍 Filter: {args.min_prob:.2f} - {args.max_prob:.2f} probability")
    print("="*70)
    print(f"\n🚀 Starting server on http://{args.host}:{args.port}")
    print(f"\n📝 Access the viewer:")
    print(f"   Local:  http://localhost:{args.port}")
    print(f"   Remote: http://<your-vm-ip>:{args.port}")
    print(f"\n💡 For SSH tunnel:")
    print(f"   ssh -L {args.port}:localhost:{args.port} user@server")
    print(f"   Then open: http://localhost:{args.port}")
    print(f"\n🛑 Press Ctrl+C to stop\n")
    print("="*70)
    
    try:
        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")


if __name__ == "__main__":
    main()
