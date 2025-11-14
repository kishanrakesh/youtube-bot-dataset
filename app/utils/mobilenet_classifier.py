#!/usr/bin/env python3
"""
MobileNetV2 inference for avatar bot classification.
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Optional, Tuple
import io

# Disable NNPACK warnings for CPU-only environments
os.environ.setdefault('NNPACK_DISABLE', '1')
# Suppress C++ level warnings from PyTorch
warnings.filterwarnings('ignore', message='.*NNPACK.*')

import cv2
import numpy as np
import requests
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

LOGGER = logging.getLogger(__name__)

_MODEL = None
_DEVICE = None


def get_device():
    """Get computing device (CPU or CUDA if available)."""
    global _DEVICE
    if _DEVICE is None:
        _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return _DEVICE


def load_mobilenet_model(model_path: str = "models/avatar/mobilenet_v2_best.pth") -> nn.Module:
    """Load trained MobileNetV2 model for inference."""
    global _MODEL
    
    if _MODEL is not None:
        return _MODEL
    
    if not Path(model_path).exists():
        raise FileNotFoundError(f"MobileNet model not found at {model_path}")
    
    # Create model architecture
    model = models.mobilenet_v2(pretrained=False)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, 2)
    
    # Load trained weights with suppressed NNPACK warnings
    device = get_device()
    
    # Suppress stderr temporarily to hide NNPACK warnings
    import sys
    from contextlib import redirect_stderr
    with open(os.devnull, 'w') as devnull:
        with redirect_stderr(devnull):
            model.load_state_dict(torch.load(model_path, map_location=device))
    
    model.to(device)
    model.eval()
    
    _MODEL = model
    LOGGER.info(f"✅ MobileNet model loaded from {model_path}")
    return model


def get_image_transform():
    """Get the image preprocessing transform for MobileNet."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])


def classify_avatar_mobilenet(
    image_input,
    model_path: str = "models/avatar/mobilenet_v2_best.pth"
) -> Tuple[str, float, dict]:
    """Classify an avatar image as bot or human using MobileNet.
    
    Args:
        image_input: URL, file path, PIL Image, or numpy array
        model_path: Path to trained model
        
    Returns:
        Tuple of (label, bot_probability, metrics)
    """
    try:
        model = load_mobilenet_model(model_path)
        device = get_device()
        transform = get_image_transform()
        
        # Load image
        img = _load_image(image_input)
        if img is None:
            return "UNKNOWN", 0.5, {"error": "Failed to load image"}
        
        # Convert to PIL if needed
        if isinstance(img, np.ndarray):
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
        
        # Transform and predict
        img_tensor = transform(img).unsqueeze(0).to(device)
        
        with torch.no_grad():
            output = model(img_tensor)
            probabilities = torch.softmax(output, dim=1)
            bot_prob = probabilities[0][0].item()
            human_prob = probabilities[0][1].item()
        
        label = "BOT" if bot_prob > 0.5 else "HUMAN"
        
        metrics = {
            "bot_probability": bot_prob,
            "human_probability": human_prob,
            "confidence": max(bot_prob, human_prob),
            "model": "mobilenet_v2",
        }
        
        return label, bot_prob, metrics
        
    except Exception as e:
        LOGGER.error(f"MobileNet classification failed: {e}")
        return "UNKNOWN", 0.5, {"error": str(e)}


def _load_image(image_input) -> Optional[Image.Image]:
    """Load image from various input types."""
    try:
        if isinstance(image_input, Image.Image):
            return image_input
        
        if isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 3 and image_input.shape[2] == 3:
                image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB)
            return Image.fromarray(image_input)
        
        if isinstance(image_input, str) and image_input.startswith(('http://', 'https://')):
            response = requests.get(image_input, timeout=10)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        
        if isinstance(image_input, (str, Path)):
            return Image.open(image_input)
        
        return None
        
    except Exception as e:
        LOGGER.error(f"Failed to load image: {e}")
        return None
