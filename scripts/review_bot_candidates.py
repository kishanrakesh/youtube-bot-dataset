#!/usr/bin/env python3
"""
Interactive reviewer for bot candidate avatars.

Shows each candidate image and asks you to label it as:
- b/bot: Confirmed bot → moves to train/bot/
- h/human: False positive → moves to train/not_bot/
- s/skip: Unsure, skip for now
- q/quit: Exit the review process

Usage:
    python scripts/review_bot_candidates.py
    python scripts/review_bot_candidates.py --candidates-dir data/new_bots
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

# Paths
DEFAULT_CANDIDATES_DIR = "data/datasets/avatar_images/bot_candidates"
TRAIN_BOT_DIR = "data/datasets/avatar_images/train/bot"
TRAIN_HUMAN_DIR = "data/datasets/avatar_images/train/not_bot"


def show_image_with_text(img: np.ndarray, filename: str, bot_prob: float) -> None:
    """Display image with filename and bot probability overlay."""
    # Create a larger display image with space for text
    display_img = img.copy()
    h, w = display_img.shape[:2]
    
    # Resize to a reasonable size for viewing
    scale = min(800 / w, 600 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    display_img = cv2.resize(display_img, (new_w, new_h))
    
    # Add white border at top for text
    border_height = 80
    bordered = np.ones((new_h + border_height, new_w, 3), dtype=np.uint8) * 255
    bordered[border_height:, :] = display_img
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(bordered, f"File: {filename}", (10, 25), font, 0.6, (0, 0, 0), 2)
    cv2.putText(bordered, f"Bot Probability: {bot_prob:.1%}", (10, 55), font, 0.7, (0, 0, 255), 2)
    
    return bordered


def review_candidates(candidates_dir: str, auto_move_threshold: float = None) -> dict:
    """Review bot candidates and move them to appropriate training folders.
    
    Args:
        candidates_dir: Directory containing bot candidate images
        auto_move_threshold: If set, auto-move images above this threshold to bot folder
        
    Returns:
        Dictionary with review statistics
    """
    candidates_path = Path(candidates_dir)
    train_bot_path = Path(TRAIN_BOT_DIR)
    train_human_path = Path(TRAIN_HUMAN_DIR)
    
    # Create directories if they don't exist
    train_bot_path.mkdir(parents=True, exist_ok=True)
    train_human_path.mkdir(parents=True, exist_ok=True)
    
    # Get all candidate images
    candidates = list(candidates_path.glob("*.jpg")) + list(candidates_path.glob("*.png"))
    
    if not candidates:
        print(f"❌ No candidate images found in {candidates_dir}")
        return {}
    
    print("\n" + "="*70)
    print("🤖 Bot Candidate Review System")
    print("="*70)
    print(f"Found {len(candidates)} candidates to review")
    print(f"\nOutput folders:")
    print(f"  Bots → {train_bot_path}")
    print(f"  Humans → {train_human_path}")
    
    if auto_move_threshold:
        print(f"\n⚡ Auto-move mode: Images with >{auto_move_threshold:.0%} probability will be auto-moved to bot folder")
    
    print("\n" + "="*70)
    print("Controls:")
    print("  b / bot   → Confirm as BOT (move to train/bot/)")
    print("  h / human → False positive, it's HUMAN (move to train/not_bot/)")
    print("  s / skip  → Skip this one (leave in candidates/)")
    print("  q / quit  → Exit review")
    print("="*70)
    print()
    
    stats = {
        'reviewed': 0,
        'moved_to_bot': 0,
        'moved_to_human': 0,
        'skipped': 0,
        'auto_moved': 0
    }
    
    for i, img_path in enumerate(candidates, 1):
        filename = img_path.name
        
        # Extract bot probability from filename (format: channelid_0.XXX.jpg)
        try:
            prob_str = filename.split('_')[-1].replace('.jpg', '').replace('.png', '')
            bot_prob = float(prob_str)
        except:
            bot_prob = 0.0
        
        # Auto-move if threshold is set and exceeded
        if auto_move_threshold and bot_prob >= auto_move_threshold:
            dest = train_bot_path / filename
            shutil.move(str(img_path), str(dest))
            stats['auto_moved'] += 1
            stats['moved_to_bot'] += 1
            print(f"[{i}/{len(candidates)}] ⚡ Auto-moved (prob={bot_prob:.1%}): {filename}")
            continue
        
        # Load and display image
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"❌ Failed to load: {filename}")
            continue
        
        display = show_image_with_text(img, filename, bot_prob)
        
        cv2.imshow('Bot Candidate Review', display)
        
        print(f"\n[{i}/{len(candidates)}] {filename} (prob={bot_prob:.1%})")
        print("Your decision (b=bot / h=human / s=skip / q=quit): ", end='', flush=True)
        
        while True:
            key = cv2.waitKey(0) & 0xFF
            
            # Bot
            if key in [ord('b'), ord('B')]:
                dest = train_bot_path / filename
                shutil.move(str(img_path), str(dest))
                stats['moved_to_bot'] += 1
                print("b → ✅ Moved to BOTS")
                break
            
            # Human
            elif key in [ord('h'), ord('H')]:
                dest = train_human_path / filename
                shutil.move(str(img_path), str(dest))
                stats['moved_to_human'] += 1
                print("h → ✅ Moved to HUMANS")
                break
            
            # Skip
            elif key in [ord('s'), ord('S')]:
                stats['skipped'] += 1
                print("s → ⏭️  Skipped")
                break
            
            # Quit
            elif key in [ord('q'), ord('Q'), 27]:  # q or ESC
                print("q → 🛑 Quitting review")
                cv2.destroyAllWindows()
                stats['reviewed'] = i - 1
                return stats
        
        stats['reviewed'] += 1
    
    cv2.destroyAllWindows()
    
    return stats


def print_summary(stats: dict):
    """Print review summary."""
    print("\n" + "="*70)
    print("📊 Review Summary")
    print("="*70)
    print(f"Total reviewed:     {stats['reviewed']}")
    print(f"Moved to bot:       {stats['moved_to_bot']} ({stats.get('auto_moved', 0)} auto)")
    print(f"Moved to human:     {stats['moved_to_human']}")
    print(f"Skipped:            {stats['skipped']}")
    print("="*70)
    
    if stats['moved_to_bot'] > 0 or stats['moved_to_human'] > 0:
        print("\n✅ Images have been added to your training dataset!")
        print("\n📝 Next steps:")
        print("1. Review more candidates, or")
        print("2. Retrain your model with the new data:")
        print("   - Package dataset: tar -czf avatar_dataset.tar.gz data/datasets/avatar_images/")
        print("   - Upload to Google Colab")
        print("   - Train with updated data")


def main():
    parser = argparse.ArgumentParser(
        description="Review bot candidate avatars and move to training folders"
    )
    parser.add_argument(
        "--candidates-dir",
        type=str,
        default=DEFAULT_CANDIDATES_DIR,
        help="Directory containing bot candidate images"
    )
    parser.add_argument(
        "--auto-threshold",
        type=float,
        default=None,
        help="Auto-move threshold (e.g., 0.9 = auto-move images with >90%% bot probability)"
    )
    
    args = parser.parse_args()
    
    # Check if OpenCV can display windows
    try:
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imshow('Test', test_img)
        cv2.waitKey(1)
        cv2.destroyAllWindows()
    except:
        print("\n❌ ERROR: Cannot display images!")
        print("This script requires a GUI environment with X11/display support.")
        print("\nIf you're on a remote server via SSH:")
        print("  1. Enable X11 forwarding: ssh -X user@server")
        print("  2. Or use the batch mode:")
        print("     python scripts/review_bot_candidates.py --auto-threshold 0.8")
        print("\nOr use the web-based reviewer instead:")
        print("  python scripts/review_bot_candidates_web.py")
        return
    
    stats = review_candidates(args.candidates_dir, args.auto_threshold)
    
    if stats:
        print_summary(stats)


if __name__ == "__main__":
    main()
