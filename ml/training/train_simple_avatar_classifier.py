#!/usr/bin/env python3
"""
Fast CPU-friendly avatar classifier using traditional ML (no deep learning).
Extracts simple visual features from avatars and trains a lightweight classifier.
"""

import cv2
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import pickle
import logging
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def extract_features(image_path):
    """Extract simple visual features from an avatar image."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    
    # Resize to standard size
    img = cv2.resize(img, (64, 64))
    
    features = []
    
    # 1. Color histogram features (RGB)
    for i in range(3):
        hist = cv2.calcHist([img], [i], None, [16], [0, 256])
        features.extend(hist.flatten())
    
    # 2. Gray histogram
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist_gray = cv2.calcHist([gray], [0], None, [16], [0, 256])
    features.extend(hist_gray.flatten())
    
    # 3. Edge density (Canny)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (64 * 64)
    features.append(edge_density)
    
    # 4. Mean and std of each channel
    for i in range(3):
        features.append(np.mean(img[:,:,i]))
        features.append(np.std(img[:,:,i]))
    
    # 5. Brightness and contrast
    features.append(np.mean(gray))
    features.append(np.std(gray))
    
    # 6. Dominant colors (simple k-means with 3 centers)
    pixels = img.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, _, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    features.extend(centers.flatten())
    
    return np.array(features)


def load_dataset(dataset_dir):
    """Load and extract features from all images."""
    dataset_path = Path(dataset_dir)
    
    X_train, y_train = [], []
    X_val, y_val = [], []
    
    # Training set
    logger.info("Loading training set...")
    for label_dir in ['bot', 'not_bot']:
        label = 0 if label_dir == 'bot' else 1
        img_dir = dataset_path / 'train' / label_dir
        
        for img_path in img_dir.glob('*.png'):
            features = extract_features(img_path)
            if features is not None:
                X_train.append(features)
                y_train.append(label)
    
    logger.info(f"  Loaded {len(X_train)} training samples")
    
    # Validation set
    logger.info("Loading validation set...")
    for label_dir in ['bot', 'not_bot']:
        label = 0 if label_dir == 'bot' else 1
        img_dir = dataset_path / 'val' / label_dir
        
        for img_path in img_dir.glob('*.png'):
            features = extract_features(img_path)
            if features is not None:
                X_val.append(features)
                y_val.append(label)
    
    logger.info(f"  Loaded {len(X_val)} validation samples")
    
    return (np.array(X_train), np.array(y_train), 
            np.array(X_val), np.array(y_val))


def evaluate_model(clf, X_train, y_train, X_val, y_val, model_name):
    """Evaluate a classifier and return metrics."""
    logger.info(f"\n📊 Evaluating {model_name}...")
    logger.info("="*60)
    
    # Training set
    train_pred = clf.predict(X_train)
    train_proba = clf.predict_proba(X_train)[:, 0]  # Probability of bot class
    train_acc = np.mean(train_pred == y_train)
    
    # Validation set
    val_pred = clf.predict(X_val)
    val_proba = clf.predict_proba(X_val)[:, 0]
    val_acc = np.mean(val_pred == y_val)
    
    logger.info(f"Training Accuracy: {train_acc:.4f}")
    logger.info(f"Validation Accuracy: {val_acc:.4f}")
    logger.info("\nClassification Report:")
    print(classification_report(y_val, val_pred, target_names=['bot', 'not_bot'], digits=4))
    
    logger.info("\nConfusion Matrix:")
    cm = confusion_matrix(y_val, val_pred)
    print(cm)
    
    # Bot-specific metrics (class 0)
    bot_recall = cm[0, 0] / (cm[0, 0] + cm[0, 1])
    bot_precision = cm[0, 0] / (cm[0, 0] + cm[1, 0])
    bot_f1 = 2 * (bot_precision * bot_recall) / (bot_precision + bot_recall)
    
    logger.info(f"\n⭐ Bot Detection Metrics:")
    logger.info(f"  Recall: {bot_recall:.4f} (catching bots)")
    logger.info(f"  Precision: {bot_precision:.4f} (avoiding false positives)")
    logger.info(f"  F1 Score: {bot_f1:.4f}")
    
    # ROC AUC
    roc_auc = roc_auc_score(y_val, val_proba)
    logger.info(f"  ROC AUC: {roc_auc:.4f}")
    
    return {
        'model_name': model_name,
        'train_acc': train_acc,
        'val_acc': val_acc,
        'bot_recall': bot_recall,
        'bot_precision': bot_precision,
        'bot_f1': bot_f1,
        'roc_auc': roc_auc,
        'confusion_matrix': cm,
    }


def main():
    logger.info("🚀 Fast Avatar Bot Classifier Training (Traditional ML)")
    logger.info("="*60)
    
    # Load data (updated path for new structure)
    dataset_path = 'data/datasets/avatar_images'
    X_train, y_train, X_val, y_val = load_dataset(dataset_path)
    
    logger.info(f"\nTraining samples: {len(X_train)} (features: {X_train.shape[1]})")
    logger.info(f"Validation samples: {len(X_val)}")
    logger.info(f"Bot class distribution: train={np.sum(y_train==0)}, val={np.sum(y_val==0)}")
    
    # Scale features for Logistic Regression and SVM
    logger.info("\n📏 Scaling features for Logistic Regression and SVM...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    results = []
    
    # ========================================================================
    # 1. Train Random Forest Classifier
    # ========================================================================
    logger.info("\n" + "="*60)
    logger.info("🌲 Training Random Forest Classifier...")
    logger.info("="*60)
    
    rf_clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',  # Handle class imbalance
        random_state=42,
        n_jobs=-1,  # Use all CPU cores
        verbose=1
    )
    
    rf_clf.fit(X_train, y_train)
    logger.info("✅ Random Forest training complete!")
    
    # Evaluate Random Forest
    rf_results = evaluate_model(rf_clf, X_train, y_train, X_val, y_val, "Random Forest")
    results.append(rf_results)
    
    # Save Random Forest model
    rf_model_path = Path('models/rf_avatar_classifier.pkl')
    rf_model_path.parent.mkdir(exist_ok=True)
    with open(rf_model_path, 'wb') as f:
        pickle.dump(rf_clf, f)
    logger.info(f"\n💾 Random Forest model saved to: {rf_model_path}")
    
    # Feature importance for Random Forest
    logger.info("\n📈 Top 10 Most Important Features (Random Forest):")
    feature_importance = rf_clf.feature_importances_
    top_indices = np.argsort(feature_importance)[-10:][::-1]
    for i, idx in enumerate(top_indices, 1):
        logger.info(f"  {i}. Feature {idx}: {feature_importance[idx]:.4f}")
    
    # ========================================================================
    # 2. Train XGBoost Classifier
    # ========================================================================
    if XGBOOST_AVAILABLE:
        logger.info("\n" + "="*60)
        logger.info("🚀 Training XGBoost Classifier...")
        logger.info("="*60)
        
        # Calculate scale_pos_weight for class imbalance
        scale_pos_weight = np.sum(y_train == 1) / np.sum(y_train == 0)
        
        xgb_clf = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,  # Handle class imbalance
            random_state=42,
            n_jobs=-1,
            eval_metric='logloss'
        )
        
        xgb_clf.fit(X_train, y_train)
        logger.info("✅ XGBoost training complete!")
        
        # Evaluate XGBoost
        xgb_results = evaluate_model(xgb_clf, X_train, y_train, X_val, y_val, "XGBoost")
        results.append(xgb_results)
        
        # Save XGBoost model
        xgb_model_path = Path('models/xgb_avatar_classifier.pkl')
        with open(xgb_model_path, 'wb') as f:
            pickle.dump(xgb_clf, f)
        logger.info(f"\n💾 XGBoost model saved to: {xgb_model_path}")
        
        # Feature importance for XGBoost
        logger.info("\n📈 Top 10 Most Important Features (XGBoost):")
        xgb_importance = xgb_clf.feature_importances_
        top_indices_xgb = np.argsort(xgb_importance)[-10:][::-1]
        for i, idx in enumerate(top_indices_xgb, 1):
            logger.info(f"  {i}. Feature {idx}: {xgb_importance[idx]:.4f}")
    else:
        logger.warning("\n⚠️  XGBoost not available. Install with: pip install xgboost")
    
    # ========================================================================
    # 3. Train Logistic Regression Classifier
    # ========================================================================
    logger.info("\n" + "="*60)
    logger.info("📊 Training Logistic Regression Classifier...")
    logger.info("="*60)
    
    lr_clf = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',  # Handle class imbalance
        random_state=42,
        n_jobs=-1,
        verbose=1
    )
    
    lr_clf.fit(X_train_scaled, y_train)
    logger.info("✅ Logistic Regression training complete!")
    
    # Evaluate Logistic Regression
    lr_results = evaluate_model(lr_clf, X_train_scaled, y_train, X_val_scaled, y_val, "Logistic Regression")
    results.append(lr_results)
    
    # Save Logistic Regression model and scaler
    lr_model_path = Path('models/lr_avatar_classifier.pkl')
    with open(lr_model_path, 'wb') as f:
        pickle.dump((lr_clf, scaler), f)  # Save both model and scaler
    logger.info(f"\n💾 Logistic Regression model saved to: {lr_model_path}")
    
    # ========================================================================
    # 4. Train SVM Classifier
    # ========================================================================
    logger.info("\n" + "="*60)
    logger.info("🎯 Training SVM Classifier...")
    logger.info("="*60)
    
    svm_clf = SVC(
        kernel='rbf',  # Radial basis function kernel for non-linear boundaries
        C=1.0,
        gamma='scale',
        class_weight='balanced',  # Handle class imbalance
        random_state=42,
        probability=True,  # Enable probability estimates for ROC AUC
        verbose=True
    )
    
    svm_clf.fit(X_train_scaled, y_train)
    logger.info("✅ SVM training complete!")
    
    # Evaluate SVM
    svm_results = evaluate_model(svm_clf, X_train_scaled, y_train, X_val_scaled, y_val, "SVM (RBF)")
    results.append(svm_results)
    
    # Save SVM model and scaler
    svm_model_path = Path('models/svm_avatar_classifier.pkl')
    with open(svm_model_path, 'wb') as f:
        pickle.dump((svm_clf, scaler), f)  # Save both model and scaler
    logger.info(f"\n💾 SVM model saved to: {svm_model_path}")
    
    # ========================================================================
    # 5. Compare Results
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("📊 MODEL COMPARISON")
    logger.info("="*80)
    
    # Print comparison table
    logger.info(f"\n{'Model':<20} {'Val Acc':<10} {'Recall':<10} {'Precision':<10} {'F1':<10} {'ROC AUC':<10}")
    logger.info("-" * 80)
    for result in results:
        logger.info(f"{result['model_name']:<20} "
                   f"{result['val_acc']:<10.4f} "
                   f"{result['bot_recall']:<10.4f} "
                   f"{result['bot_precision']:<10.4f} "
                   f"{result['bot_f1']:<10.4f} "
                   f"{result['roc_auc']:<10.4f}")
    
    # Find best model by bot recall
    best_result = max(results, key=lambda x: x['bot_recall'])
    logger.info(f"\n🏆 Best Model (by Bot Recall): {best_result['model_name']}")
    logger.info(f"   Bot Recall: {best_result['bot_recall']:.4f}")
    logger.info(f"   Bot F1 Score: {best_result['bot_f1']:.4f}")
    
    logger.info("\n✅ Training complete! These models train in seconds, not hours.")
    logger.info("💡 While not as accurate as deep learning, they're practical for CPU-only deployment.")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
