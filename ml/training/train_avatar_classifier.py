#!/usr/bin/env python3
"""
Train avatar image classifier for bot detection.

Models:
- MobileNetV2 (lightweight, production-ready)
- ResNet18 (baseline for comparison)

Optimized for:
- High recall (catch as many bots as possible)
- Class imbalance handling
- CPU training (4GB RAM)
"""

import os
import sys
import time
import json
from pathlib import Path
import logging
import numpy as np
import cv2
from collections import defaultdict

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import torchvision.models as models
from sklearn.metrics import (
    confusion_matrix, classification_report, 
    precision_recall_curve, average_precision_score,
    roc_auc_score, roc_curve
)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DATASET_DIR = Path("dataset")
MODELS_DIR = Path("models")
RESULTS_DIR = Path("results")
MODELS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Training hyperparameters
BATCH_SIZE = 32  # Increased for faster training
NUM_EPOCHS = 10  # Reduced for faster training
LEARNING_RATE = 0.001
IMG_SIZE = 224
NUM_WORKERS = 0  # CPU-only, avoid worker overhead

# Class weights (compensate for 1:1.65 imbalance)
CLASS_WEIGHTS = torch.tensor([1.65, 1.0])  # [bot, not_bot]

# Device
DEVICE = torch.device("cpu")  # CPU-only as per requirements


class AvatarDataset(Dataset):
    """Custom dataset for avatar images."""
    
    def __init__(self, data_dir, transform=None):
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.samples = []
        self.class_to_idx = {'bot': 0, 'not_bot': 1}
        
        # Load all images
        for class_name, class_idx in self.class_to_idx.items():
            class_dir = self.data_dir / class_name
            if not class_dir.exists():
                logger.warning(f"Directory {class_dir} not found!")
                continue
            
            for img_path in class_dir.glob("*.png"):
                self.samples.append((str(img_path), class_idx))
        
        logger.info(f"Loaded {len(self.samples)} samples from {data_dir}")
        
        # Log class distribution
        class_counts = defaultdict(int)
        for _, label in self.samples:
            class_counts[label] += 1
        logger.info(f"  Class distribution: bot={class_counts[0]}, not_bot={class_counts[1]}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        
        # Load image with OpenCV
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        if self.transform:
            img = self.transform(img)
        
        return img, label


def get_transforms(is_train=True):
    """Get image transforms for train/val."""
    if is_train:
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
    else:
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])


def create_model(model_name='mobilenet_v2', num_classes=2, pretrained=True):
    """Create model architecture."""
    logger.info(f"Creating model: {model_name}")
    
    if model_name == 'mobilenet_v2':
        model = models.mobilenet_v2(pretrained=pretrained)
        # Replace classifier
        model.classifier[1] = nn.Linear(model.last_channel, num_classes)
        
    elif model_name == 'resnet18':
        model = models.resnet18(pretrained=pretrained)
        # Replace fc layer
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    
    else:
        raise ValueError(f"Unknown model: {model_name}")
    
    return model


def train_epoch(model, train_loader, criterion, optimizer, device):
    """Train for one epoch."""
    import time
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    epoch_start = time.time()
    batch_times = []
    
    for i, (images, labels) in enumerate(train_loader):
        batch_start = time.time()
        
        images, labels = images.to(device), labels.to(device)
        
        # Forward pass
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        batch_time = time.time() - batch_start
        batch_times.append(batch_time)
        
        if (i + 1) % 5 == 0:
            avg_batch_time = np.mean(batch_times[-5:])
            remaining_batches = len(train_loader) - (i + 1)
            eta_seconds = remaining_batches * avg_batch_time
            eta_minutes = eta_seconds / 60
            
            logger.info(f"  Batch [{i+1}/{len(train_loader)}] "
                       f"Loss: {loss.item():.4f} "
                       f"Acc: {100.*correct/total:.2f}% "
                       f"| {batch_time:.1f}s/batch | ETA: {eta_minutes:.1f}m")
    
    epoch_time = time.time() - epoch_start
    epoch_loss = running_loss / len(train_loader)
    epoch_acc = 100. * correct / total
    
    logger.info(f"  Epoch completed in {epoch_time/60:.1f} minutes")
    return epoch_loss, epoch_acc


def validate(model, dataloader, criterion, device):
    """Validate the model."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_labels = []
    all_probs = []
    
    logger.info("  Validating...")
    with torch.no_grad():
        for images, labels in dataloader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            probs = torch.softmax(outputs, dim=1)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
    
    val_loss = running_loss / len(dataloader)
    val_acc = 100 * correct / total
    return val_loss, val_acc, np.array(all_preds), np.array(all_labels), np.array(all_probs)


def calculate_metrics(labels, predictions, probabilities, class_names=['bot', 'not_bot']):
    """Calculate comprehensive metrics."""
    metrics = {}
    
    # Basic metrics
    cm = confusion_matrix(labels, predictions)
    metrics['confusion_matrix'] = cm.tolist()
    
    # Per-class metrics
    report = classification_report(labels, predictions, target_names=class_names, output_dict=True)
    metrics['classification_report'] = report
    
    # Bot class metrics (class 0)
    bot_precision = report['bot']['precision']
    bot_recall = report['bot']['recall']
    bot_f1 = report['bot']['f1-score']
    
    metrics['bot_precision'] = bot_precision
    metrics['bot_recall'] = bot_recall
    metrics['bot_f1'] = bot_f1
    
    # ROC AUC
    try:
        auc = roc_auc_score(labels, probabilities[:, 0])  # Prob of bot class
        metrics['roc_auc'] = auc
    except:
        metrics['roc_auc'] = None
    
    # PR AUC (for imbalanced classes)
    try:
        pr_auc = average_precision_score(labels == 0, probabilities[:, 0])  # Bot class
        metrics['pr_auc'] = pr_auc
    except:
        metrics['pr_auc'] = None
    
    return metrics


def plot_metrics(metrics, model_name, save_dir):
    """Plot confusion matrix and PR curve."""
    # Confusion matrix
    cm = np.array(metrics['confusion_matrix'])
    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(f'Confusion Matrix - {model_name}')
    plt.colorbar()
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, ['bot', 'not_bot'])
    plt.yticks(tick_marks, ['bot', 'not_bot'])
    
    # Add text annotations
    thresh = cm.max() / 2.
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], 'd'),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    plt.savefig(save_dir / f'{model_name}_confusion_matrix.png')
    plt.close()
    
    logger.info(f"Saved confusion matrix plot to {save_dir}")


def train_model(model_name='mobilenet_v2'):
    """Main training function."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Training {model_name.upper()}")
    logger.info(f"{'='*60}\n")
    
    # Create datasets
    train_dataset = AvatarDataset(DATASET_DIR / 'train', transform=get_transforms(is_train=True))
    val_dataset = AvatarDataset(DATASET_DIR / 'val', transform=get_transforms(is_train=False))
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, 
                             shuffle=True, num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, 
                           shuffle=False, num_workers=NUM_WORKERS)
    
    # Create model
    model = create_model(model_name, num_classes=2, pretrained=True)
    model = model.to(DEVICE)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss(weight=CLASS_WEIGHTS.to(DEVICE))
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', 
                                                      factor=0.5, patience=3)
    
    # Training loop
    best_val_recall = 0.0
    training_history = []
    
    for epoch in range(NUM_EPOCHS):
        logger.info(f"\nEpoch [{epoch+1}/{NUM_EPOCHS}]")
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, DEVICE)
        
        # Validate
        val_loss, val_acc, val_labels, val_preds, val_probs = validate(
            model, val_loader, criterion, DEVICE)
        
        # Calculate metrics
        metrics = calculate_metrics(val_labels, val_preds, val_probs)
        
        logger.info(f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        logger.info(f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")
        logger.info(f"Bot Recall: {metrics['bot_recall']:.4f} | "
                   f"Bot Precision: {metrics['bot_precision']:.4f} | "
                   f"Bot F1: {metrics['bot_f1']:.4f}")
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        # Save history
        training_history.append({
            'epoch': epoch + 1,
            'train_loss': train_loss,
            'train_acc': train_acc,
            'val_loss': val_loss,
            'val_acc': val_acc,
            'bot_recall': metrics['bot_recall'],
            'bot_precision': metrics['bot_precision'],
            'bot_f1': metrics['bot_f1']
        })
        
        # Save best model based on recall
        if metrics['bot_recall'] > best_val_recall:
            best_val_recall = metrics['bot_recall']
            model_path = MODELS_DIR / f'{model_name}_bot_classifier.pth'
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_recall': best_val_recall,
                'metrics': metrics
            }, model_path)
            logger.info(f"✅ Saved best model (recall={best_val_recall:.4f}) to {model_path}")
    
    # Final evaluation
    logger.info(f"\n{'='*60}")
    logger.info(f"FINAL RESULTS - {model_name.upper()}")
    logger.info(f"{'='*60}")
    
    # Load best model
    checkpoint = torch.load(MODELS_DIR / f'{model_name}_bot_classifier.pth')
    model.load_state_dict(checkpoint['model_state_dict'])
    
    # Evaluate
    val_loss, val_acc, val_labels, val_preds, val_probs = validate(
        model, val_loader, criterion, DEVICE)
    final_metrics = calculate_metrics(val_labels, val_preds, val_probs)
    
    # Print detailed report
    logger.info("\nClassification Report:")
    logger.info(classification_report(val_labels, val_preds, target_names=['bot', 'not_bot']))
    
    logger.info("\nConfusion Matrix:")
    cm = np.array(final_metrics['confusion_matrix'])
    logger.info(f"                Predicted")
    logger.info(f"              bot  not_bot")
    logger.info(f"Actual bot    {cm[0,0]:3d}  {cm[0,1]:3d}")
    logger.info(f"       not_bot{cm[1,0]:3d}  {cm[1,1]:3d}")
    
    logger.info(f"\nKey Metrics:")
    logger.info(f"  Bot Recall: {final_metrics['bot_recall']:.4f}")
    logger.info(f"  Bot Precision: {final_metrics['bot_precision']:.4f}")
    logger.info(f"  Bot F1-Score: {final_metrics['bot_f1']:.4f}")
    logger.info(f"  ROC AUC: {final_metrics['roc_auc']:.4f if final_metrics['roc_auc'] else 'N/A'}")
    logger.info(f"  PR AUC: {final_metrics['pr_auc']:.4f if final_metrics['pr_auc'] else 'N/A'}")
    
    # Save results
    results = {
        'model_name': model_name,
        'final_metrics': final_metrics,
        'training_history': training_history,
        'config': {
            'batch_size': BATCH_SIZE,
            'num_epochs': NUM_EPOCHS,
            'learning_rate': LEARNING_RATE,
            'img_size': IMG_SIZE,
            'class_weights': CLASS_WEIGHTS.tolist()
        }
    }
    
    with open(RESULTS_DIR / f'{model_name}_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Plot
    plot_metrics(final_metrics, model_name, RESULTS_DIR)
    
    logger.info(f"\n✅ Results saved to {RESULTS_DIR}")
    
    return final_metrics, training_history


def main():
    logger.info("🚀 Avatar Bot Classifier Training")
    logger.info(f"Device: {DEVICE}")
    logger.info(f"Dataset: {DATASET_DIR}")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info(f"Epochs: {NUM_EPOCHS}\n")
    
    # Train MobileNetV2 (lightweight) only - ResNet too slow on CPU
    logger.info("\n" + "🔵 TRAINING MOBILENETV2 (Lightweight)")
    mobilenet_metrics, _ = train_model('mobilenet_v2')
    
    # Skip ResNet18 on CPU-only training
    logger.info("\n" + "⏭️  Skipping ResNet18 (too slow on CPU)")
    
    # Show results
    logger.info("\n" + "="*60)
    logger.info("📊 FINAL RESULTS")
    logger.info("="*60)
    logger.info(f"\nMobileNetV2:")
    logger.info(f"  Bot Recall: {mobilenet_metrics['bot_recall']:.4f} ⭐ (primary metric)")
    logger.info(f"  Bot Precision: {mobilenet_metrics['bot_precision']:.4f}")
    logger.info(f"  Bot F1: {mobilenet_metrics['bot_f1']:.4f}")
    
    logger.info("\n✅ Training complete! Model saved to models/mobilenet_v2_best.pth")
    return 0


if __name__ == "__main__":
    sys.exit(main())
