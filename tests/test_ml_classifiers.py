#!/usr/bin/env python3
"""
Test ML classifiers and store results.

Runs:
1. Traditional ML classifiers (Random Forest, Logistic Regression, SVM, XGBoost)
2. MobileNetV2 classifier (if dataset available)

Stores results in test_results/ directory.
"""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path("test_results")
RESULTS_DIR.mkdir(exist_ok=True)


def test_traditional_ml_classifier():
    """Test traditional ML classifier (Random Forest, Logistic Regression, SVM, XGBoost)."""
    logger.info("="*80)
    logger.info("Testing Traditional ML Classifiers")
    logger.info("="*80)
    
    try:
        # Import and run the training script
        from ml.training.avatar import train_simple_avatar_classifier
        
        # Capture the results by monkey-patching the main function
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "traditional_ml_classifier",
            "status": "running"
        }
        
        # Run training
        train_simple_avatar_classifier.main()
        
        results["status"] = "success"
        logger.info("✅ Traditional ML classifier test completed")
        
    except Exception as e:
        logger.exception(f"❌ Traditional ML classifier test failed: {e}")
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "traditional_ml_classifier",
            "status": "failed",
            "error": str(e)
        }
    
    # Save results
    result_file = RESULTS_DIR / f"traditional_ml_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📊 Results saved to: {result_file}")
    return results


def test_mobilenet_classifier():
    """Test MobileNetV2 classifier."""
    logger.info("="*80)
    logger.info("Testing MobileNetV2 Classifier")
    logger.info("="*80)
    
    try:
        # Check if dataset exists
        dataset_dir = Path("data/datasets/avatar_images")
        if not dataset_dir.exists():
            logger.warning(f"⚠️ Dataset not found at {dataset_dir}")
            logger.info("Run: python ml/utils/export_avatar_dataset.py first")
            return {
                "timestamp": datetime.now().isoformat(),
                "test_type": "mobilenet_classifier",
                "status": "skipped",
                "reason": "dataset_not_found"
            }
        
        # Import and run the training script
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ml.training.avatar import train_avatar_classifier
        
        # Update DATASET_DIR in the training script to use correct path
        train_avatar_classifier.DATASET_DIR = dataset_dir
        
        # Update the DATASET_DIR in the training module
        train_avatar_classifier.DATASET_DIR = dataset_dir
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "mobilenet_classifier",
            "status": "running"
        }
        
        # Run training
        train_avatar_classifier.train_model('mobilenet_v2')
        
        results["status"] = "success"
        logger.info("✅ MobileNetV2 classifier test completed")
        
    except Exception as e:
        logger.exception(f"❌ MobileNetV2 classifier test failed: {e}")
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "mobilenet_classifier",
            "status": "failed",
            "error": str(e)
        }
    
    # Save results
    result_file = RESULTS_DIR / f"mobilenet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📊 Results saved to: {result_file}")
    return results


def test_inference():
    """Test inference with trained models."""
    logger.info("="*80)
    logger.info("Testing Model Inference")
    logger.info("="*80)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_type": "inference",
        "models_tested": []
    }
    
    # Test MobileNet inference
    try:
        from app.utils.mobilenet_classifier import classify_avatar_mobilenet
        from app.utils.image_processing import is_mobilenet_available
        
        if is_mobilenet_available():
            # Create a dummy test image
            import numpy as np
            import cv2
            
            # Create a simple test image (88x88 gray square)
            test_img = np.ones((88, 88, 3), dtype=np.uint8) * 128
            
            label, bot_prob, metrics = classify_avatar_mobilenet(test_img)
            
            results["models_tested"].append({
                "model": "mobilenet_v2",
                "status": "success",
                "test_label": label,
                "test_bot_prob": bot_prob,
                "metrics": metrics
            })
            logger.info(f"✅ MobileNet inference: {label} (bot_prob={bot_prob:.4f})")
        else:
            results["models_tested"].append({
                "model": "mobilenet_v2",
                "status": "skipped",
                "reason": "model_not_available"
            })
            logger.warning("⚠️ MobileNet model not available")
            
    except Exception as e:
        logger.exception(f"❌ MobileNet inference failed: {e}")
        results["models_tested"].append({
            "model": "mobilenet_v2",
            "status": "failed",
            "error": str(e)
        })
    
    # Test traditional classifier inference
    try:
        from app.utils.image_processing import classify_avatar_url
        
        # Test with a dummy URL (will fail to download but test the flow)
        label, metrics = classify_avatar_url(
            "https://yt3.ggpht.com/test",
            use_mobilenet=False
        )
        
        results["models_tested"].append({
            "model": "traditional_classifier",
            "status": "success",
            "test_label": label,
            "metrics": {k: v for k, v in metrics.items() if isinstance(v, (int, float, str, bool))}
        })
        logger.info(f"✅ Traditional classifier inference: {label}")
        
    except Exception as e:
        logger.exception(f"❌ Traditional classifier inference failed: {e}")
        results["models_tested"].append({
            "model": "traditional_classifier",
            "status": "failed",
            "error": str(e)
        })
    
    # Save results
    result_file = RESULTS_DIR / f"inference_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📊 Results saved to: {result_file}")
    return results


def main():
    """Run all ML classifier tests."""
    logger.info("🚀 Starting ML Classifier Tests")
    logger.info("="*80)
    
    all_results = {
        "test_suite": "ml_classifiers",
        "start_time": datetime.now().isoformat(),
        "tests": []
    }
    
    # Run tests
    try:
        # Test 1: Traditional ML
        logger.info("\n📊 Test 1: Traditional ML Classifiers")
        result1 = test_traditional_ml_classifier()
        all_results["tests"].append(result1)
        
        # Test 2: MobileNet (optional, requires dataset)
        logger.info("\n📊 Test 2: MobileNetV2 Classifier")
        result2 = test_mobilenet_classifier()
        all_results["tests"].append(result2)
        
        # Test 3: Inference
        logger.info("\n📊 Test 3: Model Inference")
        result3 = test_inference()
        all_results["tests"].append(result3)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Tests interrupted by user")
        all_results["status"] = "interrupted"
    except Exception as e:
        logger.exception(f"💥 Test suite failed: {e}")
        all_results["status"] = "failed"
        all_results["error"] = str(e)
    else:
        all_results["status"] = "completed"
    
    all_results["end_time"] = datetime.now().isoformat()
    
    # Save summary
    summary_file = RESULTS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info("="*80)
    logger.info(f"📊 Test suite completed: {all_results['status']}")
    logger.info(f"📁 Summary saved to: {summary_file}")
    logger.info("="*80)
    
    return all_results


if __name__ == "__main__":
    main()
