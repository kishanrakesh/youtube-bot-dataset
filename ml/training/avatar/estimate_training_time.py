#!/usr/bin/env python3
"""
Quick test to estimate MobileNetV2 training time on CPU.
Runs just 10 batches to measure speed.
"""

import sys
import time
import torch
import torchvision
from pathlib import Path
from torch.utils.data import DataLoader
from torchvision import transforms
import logging

# Import from train_avatar_classifier
sys.path.insert(0, str(Path(__file__).parent))
from train_avatar_classifier import AvatarDataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 32
IMG_SIZE = 224
NUM_TEST_BATCHES = 10

def main():
    logger.info("🔬 MobileNetV2 Training Speed Test")
    logger.info("="*60)
    
    # Setup
    device = torch.device("cpu")
    
    # Load small dataset
    train_transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    dataset = AvatarDataset(Path("dataset/train"), transform=train_transform)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    
    logger.info(f"Dataset size: {len(dataset)} samples")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info(f"Total batches per epoch: {len(dataloader)}")
    logger.info(f"Testing with first {NUM_TEST_BATCHES} batches...\n")
    
    # Create model
    model = torchvision.models.mobilenet_v2(pretrained=True)
    model.classifier[1] = torch.nn.Linear(model.last_channel, 2)
    model = model.to(device)
    
    # Setup training
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    # Test batches
    model.train()
    batch_times = []
    
    logger.info("Starting batch timing test...")
    for i, (images, labels) in enumerate(dataloader):
        if i >= NUM_TEST_BATCHES:
            break
        
        batch_start = time.time()
        
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        batch_time = time.time() - batch_start
        batch_times.append(batch_time)
        
        logger.info(f"  Batch {i+1}/{NUM_TEST_BATCHES}: {batch_time:.2f}s | Loss: {loss.item():.4f}")
    
    # Calculate estimates
    avg_batch_time = sum(batch_times) / len(batch_times)
    total_batches = len(dataloader)
    
    logger.info("\n" + "="*60)
    logger.info("📊 TIMING ESTIMATES")
    logger.info("="*60)
    logger.info(f"Average batch time: {avg_batch_time:.2f} seconds")
    logger.info(f"Batches per epoch: {total_batches}")
    
    time_per_epoch = avg_batch_time * total_batches
    logger.info(f"\n⏱️  Estimated time per epoch: {time_per_epoch/60:.1f} minutes ({time_per_epoch:.0f} seconds)")
    
    total_epochs = 10
    total_time = time_per_epoch * total_epochs
    logger.info(f"⏱️  Estimated total time for {total_epochs} epochs: {total_time/3600:.1f} hours ({total_time/60:.0f} minutes)")
    
    if total_time > 3600:
        logger.info("\n⚠️  WARNING: Training will take over 1 hour on CPU!")
        logger.info("💡 Consider using the Random Forest model (15 seconds) instead.")
    elif total_time > 1800:
        logger.info("\n⚠️  Training will take 30+ minutes. Consider running overnight.")
    else:
        logger.info("\n✅ Training time is reasonable. You can proceed!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
