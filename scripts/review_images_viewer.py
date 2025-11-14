#!/usr/bin/env python3
"""
Configurable Image Viewer for reviewing scraped avatar images.

Features:
- View images from any directory with custom configuration
- Multiple view modes: grid, slideshow, interactive
- Filter by bot probability threshold
- Sort by probability, filename, or random
- Customizable display size and layout
- Metadata overlay (filename, probability, dimensions)

Usage:
    # Interactive review (like original script)
    python scripts/review_images_viewer.py --mode interactive
    
    # Grid view of bot candidates
    python scripts/review_images_viewer.py --mode grid --source bot_candidates
    
    # Slideshow of high probability bots
    python scripts/review_images_viewer.py --mode slideshow --min-prob 0.8
    
    # View training data
    python scripts/review_images_viewer.py --source train/bot --mode grid
    
    # Custom configuration
    python scripts/review_images_viewer.py --source bot_candidates --mode grid \
        --grid-cols 5 --grid-rows 4 --img-size 150 --sort prob-desc
"""

import argparse
import os
import random
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import time

import cv2
import numpy as np


class ImageViewerConfig:
    """Configuration for the image viewer."""
    
    def __init__(self, **kwargs):
        # Source directory
        self.source_dir = kwargs.get('source_dir', 'data/datasets/avatar_images/bot_candidates')
        
        # View mode
        self.mode = kwargs.get('mode', 'interactive')  # interactive, grid, slideshow
        
        # Filtering
        self.min_prob = kwargs.get('min_prob', 0.0)
        self.max_prob = kwargs.get('max_prob', 1.0)
        self.pattern = kwargs.get('pattern', '*')  # filename pattern
        
        # Sorting
        self.sort_by = kwargs.get('sort_by', 'prob-desc')  # prob-asc, prob-desc, name, random
        
        # Display settings
        self.img_size = kwargs.get('img_size', 200)  # size for grid thumbnails
        self.grid_cols = kwargs.get('grid_cols', 4)
        self.grid_rows = kwargs.get('grid_rows', 3)
        self.slideshow_delay = kwargs.get('slideshow_delay', 2.0)  # seconds
        
        # Overlay settings
        self.show_filename = kwargs.get('show_filename', True)
        self.show_prob = kwargs.get('show_prob', True)
        self.show_dims = kwargs.get('show_dims', False)
        self.show_index = kwargs.get('show_index', True)
        
        # Interactive mode settings
        self.single_image_max_size = kwargs.get('single_image_max_size', (800, 600))


class ImageInfo:
    """Information about an image file."""
    
    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.bot_prob = self._extract_prob()
        self.img = None
        self.width = None
        self.height = None
    
    def _extract_prob(self) -> float:
        """Extract bot probability from filename."""
        try:
            # Format: channelid_0.XXX.jpg
            prob_str = self.filename.split('_')[-1]
            prob_str = prob_str.replace('.jpg', '').replace('.png', '')
            return float(prob_str)
        except:
            return 0.0
    
    def load(self):
        """Load the image."""
        if self.img is None:
            self.img = cv2.imread(str(self.path))
            if self.img is not None:
                self.height, self.width = self.img.shape[:2]
    
    def get_display_img(self, size: int, config: ImageViewerConfig) -> np.ndarray:
        """Get resized image with overlay."""
        if self.img is None:
            self.load()
        
        if self.img is None:
            # Create error placeholder
            return np.zeros((size, size, 3), dtype=np.uint8)
        
        # Resize maintaining aspect ratio
        h, w = self.img.shape[:2]
        scale = min(size / w, size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(self.img, (new_w, new_h))
        
        # Create canvas
        canvas = np.ones((size, size, 3), dtype=np.uint8) * 240
        
        # Center image
        y_offset = (size - new_h) // 2
        x_offset = (size - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return canvas
    
    def __repr__(self):
        return f"ImageInfo({self.filename}, prob={self.bot_prob:.2f})"


class ImageViewer:
    """Main image viewer class."""
    
    def __init__(self, config: ImageViewerConfig):
        self.config = config
        self.images: List[ImageInfo] = []
        self.current_index = 0
    
    def load_images(self):
        """Load images from the configured source directory."""
        source_path = Path(self.config.source_dir)
        
        if not source_path.exists():
            print(f"❌ Directory not found: {source_path}")
            return
        
        # Find all image files
        patterns = ['*.jpg', '*.png', '*.jpeg', '*.JPG', '*.PNG']
        all_files = []
        for pattern in patterns:
            all_files.extend(source_path.glob(pattern))
        
        if not all_files:
            print(f"❌ No images found in {source_path}")
            return
        
        # Create ImageInfo objects
        for path in all_files:
            img_info = ImageInfo(path)
            
            # Apply filters
            if self.config.min_prob <= img_info.bot_prob <= self.config.max_prob:
                self.images.append(img_info)
        
        if not self.images:
            print(f"❌ No images match the filters (min_prob={self.config.min_prob}, max_prob={self.config.max_prob})")
            return
        
        # Sort images
        self._sort_images()
        
        print(f"✅ Loaded {len(self.images)} images from {source_path}")
        if len(self.images) < len(all_files):
            print(f"   (filtered from {len(all_files)} total)")
    
    def _sort_images(self):
        """Sort images based on configuration."""
        if self.config.sort_by == 'prob-desc':
            self.images.sort(key=lambda x: x.bot_prob, reverse=True)
        elif self.config.sort_by == 'prob-asc':
            self.images.sort(key=lambda x: x.bot_prob)
        elif self.config.sort_by == 'name':
            self.images.sort(key=lambda x: x.filename)
        elif self.config.sort_by == 'random':
            random.shuffle(self.images)
    
    def run(self):
        """Run the viewer in the configured mode."""
        if not self.images:
            print("No images to display")
            return
        
        print(f"\n🖼️  Image Viewer - {self.config.mode.upper()} mode")
        print("="*70)
        
        if self.config.mode == 'grid':
            self.run_grid_mode()
        elif self.config.mode == 'slideshow':
            self.run_slideshow_mode()
        elif self.config.mode == 'interactive':
            self.run_interactive_mode()
        else:
            print(f"❌ Unknown mode: {self.config.mode}")
    
    def run_grid_mode(self):
        """Display images in a grid."""
        cols = self.config.grid_cols
        rows = self.config.grid_rows
        img_size = self.config.img_size
        
        total_images = len(self.images)
        images_per_page = cols * rows
        total_pages = (total_images + images_per_page - 1) // images_per_page
        
        print(f"Displaying {total_images} images in {cols}x{rows} grid")
        print(f"Total pages: {total_pages}")
        print("\nControls:")
        print("  n / → : Next page")
        print("  p / ← : Previous page")
        print("  q / ESC : Quit")
        print("="*70)
        
        page = 0
        
        while True:
            # Create grid
            grid = self._create_grid(page, cols, rows, img_size)
            
            # Show grid
            cv2.imshow(f'Grid View - Page {page+1}/{total_pages}', grid)
            
            # Wait for key
            key = cv2.waitKey(0) & 0xFF
            
            if key in [ord('n'), ord('N'), 83]:  # n or right arrow
                page = min(page + 1, total_pages - 1)
            elif key in [ord('p'), ord('P'), 81]:  # p or left arrow
                page = max(page - 1, 0)
            elif key in [ord('q'), ord('Q'), 27]:  # q or ESC
                break
        
        cv2.destroyAllWindows()
    
    def _create_grid(self, page: int, cols: int, rows: int, img_size: int) -> np.ndarray:
        """Create a grid of images for the given page."""
        images_per_page = cols * rows
        start_idx = page * images_per_page
        end_idx = min(start_idx + images_per_page, len(self.images))
        
        # Create grid canvas
        padding = 10
        cell_size = img_size + padding
        grid_width = cols * cell_size
        grid_height = rows * cell_size + 60  # Extra space for title
        grid = np.ones((grid_height, grid_width, 3), dtype=np.uint8) * 255
        
        # Add title bar
        font = cv2.FONT_HERSHEY_SIMPLEX
        title = f"Page {page+1} | Images {start_idx+1}-{end_idx} of {len(self.images)}"
        cv2.putText(grid, title, (10, 35), font, 0.8, (0, 0, 0), 2)
        
        # Place images in grid
        for i, img_idx in enumerate(range(start_idx, end_idx)):
            row = i // cols
            col = i % cols
            
            img_info = self.images[img_idx]
            img_info.load()
            
            # Get display image
            display_img = img_info.get_display_img(img_size, self.config)
            
            # Add text overlay
            if self.config.show_index or self.config.show_prob or self.config.show_filename:
                overlay = display_img.copy()
                
                # Semi-transparent black bar at bottom
                bar_height = 35
                cv2.rectangle(overlay, (0, img_size - bar_height), (img_size, img_size), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, display_img, 0.4, 0, display_img)
                
                # Add text
                y_text = img_size - 10
                if self.config.show_prob:
                    text = f"{img_info.bot_prob:.2f}"
                    cv2.putText(display_img, text, (5, y_text), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.5, (255, 255, 255), 1)
                
                if self.config.show_index:
                    text = f"#{img_idx+1}"
                    cv2.putText(display_img, text, (img_size - 50, y_text), cv2.FONT_HERSHEY_SIMPLEX,
                               0.5, (255, 255, 255), 1)
            
            # Place in grid
            y_pos = 60 + row * cell_size + padding // 2
            x_pos = col * cell_size + padding // 2
            grid[y_pos:y_pos+img_size, x_pos:x_pos+img_size] = display_img
        
        return grid
    
    def run_slideshow_mode(self):
        """Display images in slideshow mode."""
        print(f"Slideshow: {len(self.images)} images, {self.config.slideshow_delay}s per image")
        print("\nControls:")
        print("  SPACE : Pause/Resume")
        print("  n / → : Next image")
        print("  p / ← : Previous image")
        print("  q / ESC : Quit")
        print("="*70)
        
        paused = False
        
        for idx in range(len(self.images)):
            img_info = self.images[idx]
            img_info.load()
            
            if img_info.img is None:
                continue
            
            # Create display
            display = self._create_single_image_display(img_info, idx)
            
            cv2.imshow('Slideshow', display)
            
            # Handle pause and navigation
            if paused:
                key = cv2.waitKey(0) & 0xFF
            else:
                wait_ms = int(self.config.slideshow_delay * 1000)
                key = cv2.waitKey(wait_ms) & 0xFF
            
            if key == ord(' '):  # Space to pause
                paused = not paused
                idx -= 1  # Stay on same image
            elif key in [ord('n'), ord('N'), 83]:  # Next
                continue
            elif key in [ord('p'), ord('P'), 81]:  # Previous
                idx = max(0, idx - 2)
            elif key in [ord('q'), ord('Q'), 27]:  # Quit
                break
        
        cv2.destroyAllWindows()
    
    def run_interactive_mode(self):
        """Display images one at a time with detailed info."""
        print(f"Interactive mode: {len(self.images)} images")
        print("\nControls:")
        print("  n / → / SPACE : Next image")
        print("  p / ← : Previous image")
        print("  1-9 : Jump to image at that percentage (1=10%, 5=50%, 9=90%)")
        print("  g : Jump to specific index")
        print("  i : Toggle info display")
        print("  q / ESC : Quit")
        print("="*70)
        
        show_info = True
        
        while True:
            if self.current_index < 0:
                self.current_index = 0
            elif self.current_index >= len(self.images):
                self.current_index = len(self.images) - 1
            
            img_info = self.images[self.current_index]
            img_info.load()
            
            if img_info.img is None:
                print(f"Failed to load: {img_info.filename}")
                self.current_index += 1
                continue
            
            # Create display
            display = self._create_single_image_display(img_info, self.current_index, show_info)
            
            cv2.imshow('Image Viewer', display)
            
            # Print info to console
            print(f"\n[{self.current_index+1}/{len(self.images)}] {img_info.filename}")
            print(f"  Bot probability: {img_info.bot_prob:.2%}")
            print(f"  Dimensions: {img_info.width}x{img_info.height}px")
            
            # Wait for key
            key = cv2.waitKey(0) & 0xFF
            
            if key in [ord('n'), ord('N'), ord(' '), 83]:  # Next
                self.current_index += 1
            elif key in [ord('p'), ord('P'), 81]:  # Previous
                self.current_index -= 1
            elif key in [ord('i'), ord('I')]:  # Toggle info
                show_info = not show_info
            elif key in [ord('g'), ord('G')]:  # Go to index
                try:
                    cv2.destroyWindow('Image Viewer')
                    idx = int(input(f"Enter index (1-{len(self.images)}): ")) - 1
                    self.current_index = max(0, min(idx, len(self.images) - 1))
                except:
                    pass
            elif key >= ord('1') and key <= ord('9'):  # Jump to percentage
                percentage = (key - ord('0')) * 10
                self.current_index = int(len(self.images) * percentage / 100)
            elif key in [ord('q'), ord('Q'), 27]:  # Quit
                break
        
        cv2.destroyAllWindows()
    
    def _create_single_image_display(self, img_info: ImageInfo, index: int, show_info: bool = True) -> np.ndarray:
        """Create display for a single image."""
        img = img_info.img.copy()
        h, w = img.shape[:2]
        
        # Resize to fit display
        max_w, max_h = self.config.single_image_max_size
        scale = min(max_w / w, max_h / h, 1.0)
        new_w, new_h = int(w * scale), int(h * scale)
        
        if scale < 1.0:
            img = cv2.resize(img, (new_w, new_h))
        
        if not show_info:
            return img
        
        # Add info bar at top
        bar_height = 100
        display = np.ones((new_h + bar_height, new_w, 3), dtype=np.uint8) * 255
        display[bar_height:, :] = img
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        y = 25
        
        cv2.putText(display, f"[{index+1}/{len(self.images)}] {img_info.filename[:50]}", 
                   (10, y), font, 0.6, (0, 0, 0), 2)
        y += 30
        
        # Bot probability with color coding
        prob_color = (0, 0, 255) if img_info.bot_prob > 0.7 else (0, 165, 255) if img_info.bot_prob > 0.5 else (0, 128, 0)
        cv2.putText(display, f"Bot Probability: {img_info.bot_prob:.1%}", 
                   (10, y), font, 0.8, prob_color, 2)
        y += 30
        
        cv2.putText(display, f"Original size: {img_info.width}x{img_info.height}px", 
                   (10, y), font, 0.5, (100, 100, 100), 1)
        
        return display


def main():
    parser = argparse.ArgumentParser(
        description="Configurable image viewer for scraped avatars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Grid view of bot candidates
  python scripts/review_images_viewer.py --mode grid --source bot_candidates
  
  # Slideshow of high-confidence bots
  python scripts/review_images_viewer.py --mode slideshow --min-prob 0.8
  
  # Interactive review of training bots
  python scripts/review_images_viewer.py --source train/bot
  
  # Large grid of all candidates
  python scripts/review_images_viewer.py --mode grid --grid-cols 6 --grid-rows 5
        """
    )
    
    # Source and filtering
    parser.add_argument('--source', type=str, 
                       default='bot_candidates',
                       help='Source directory (relative to data/datasets/avatar_images/ or absolute path)')
    parser.add_argument('--min-prob', type=float, default=0.0,
                       help='Minimum bot probability filter (0.0-1.0)')
    parser.add_argument('--max-prob', type=float, default=1.0,
                       help='Maximum bot probability filter (0.0-1.0)')
    
    # View mode
    parser.add_argument('--mode', type=str, default='interactive',
                       choices=['interactive', 'grid', 'slideshow'],
                       help='Viewing mode')
    
    # Sorting
    parser.add_argument('--sort', type=str, default='prob-desc',
                       choices=['prob-desc', 'prob-asc', 'name', 'random'],
                       help='Sort order')
    
    # Grid settings
    parser.add_argument('--grid-cols', type=int, default=4,
                       help='Number of columns in grid mode')
    parser.add_argument('--grid-rows', type=int, default=3,
                       help='Number of rows in grid mode')
    parser.add_argument('--img-size', type=int, default=200,
                       help='Thumbnail size in grid mode')
    
    # Slideshow settings
    parser.add_argument('--slideshow-delay', type=float, default=2.0,
                       help='Delay between images in slideshow (seconds)')
    
    # Display options
    parser.add_argument('--no-filename', action='store_true',
                       help='Hide filename overlay')
    parser.add_argument('--no-prob', action='store_true',
                       help='Hide probability overlay')
    parser.add_argument('--show-dims', action='store_true',
                       help='Show image dimensions overlay')
    parser.add_argument('--no-index', action='store_true',
                       help='Hide index overlay')
    
    args = parser.parse_args()
    
    # Resolve source directory
    if not args.source.startswith('/'):
        source_dir = f"data/datasets/avatar_images/{args.source}"
    else:
        source_dir = args.source
    
    # Check if OpenCV can display windows
    if args.mode in ['grid', 'slideshow', 'interactive']:
        try:
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imshow('Test', test_img)
            cv2.waitKey(1)
            cv2.destroyAllWindows()
        except:
            print("\n❌ ERROR: Cannot display images!")
            print("This script requires a GUI environment with X11/display support.")
            print("\nIf you're on a remote server via SSH, enable X11 forwarding:")
            print("  ssh -X user@server")
            return
    
    # Create configuration
    config = ImageViewerConfig(
        source_dir=source_dir,
        mode=args.mode,
        min_prob=args.min_prob,
        max_prob=args.max_prob,
        sort_by=args.sort,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
        img_size=args.img_size,
        slideshow_delay=args.slideshow_delay,
        show_filename=not args.no_filename,
        show_prob=not args.no_prob,
        show_dims=args.show_dims,
        show_index=not args.no_index,
    )
    
    # Create and run viewer
    viewer = ImageViewer(config)
    viewer.load_images()
    
    if viewer.images:
        viewer.run()
        print("\n✅ Viewer closed")
    else:
        print("\n❌ No images to display")


if __name__ == "__main__":
    main()
