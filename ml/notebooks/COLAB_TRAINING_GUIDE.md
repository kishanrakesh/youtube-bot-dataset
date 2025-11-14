# Training Avatar Classifier on Google Colab

## Quick Start Guide

### 1. Download the Dataset
On your VPS, the dataset has been prepared and zipped:
```bash
ls -lh /root/youtube-bot-dataset/dataset.zip
```

Download this file to your local machine using SCP or your file manager.

### 2. Open Google Colab
1. Go to https://colab.research.google.com/
2. Sign in with your Google account
3. Click **File → Upload notebook**
4. Upload `/root/youtube-bot-dataset/train_avatar_colab.ipynb`

### 3. Enable GPU
1. Click **Runtime → Change runtime type**
2. Select **GPU** from the Hardware accelerator dropdown
3. Click **Save**

### 4. Run the Notebook
1. Click on the first cell and press **Shift+Enter** (or click the play button)
2. Continue running each cell in order
3. When prompted, upload `dataset.zip` (the file you downloaded)
4. Training will complete in **5-10 minutes** on GPU (vs hours on CPU!)

### 5. Download Results
The final cell will download:
- `mobilenet_v2_best.pth` - Your trained model
- `training_history.png` - Training graphs

## Expected Results

With GPU training, you should see significantly better results than the Random Forest:
- **Bot Recall**: 85-95% (vs 73.5% with Random Forest)
- **Training Time**: 5-10 minutes (vs 1+ hour on CPU)
- **Model Size**: ~14MB

## Using the Trained Model

Once you download the `.pth` file, upload it back to your VPS and use this inference script:

```python
import torch
import torchvision
import cv2
from torchvision import transforms

# Load model
model = torchvision.models.mobilenet_v2(pretrained=False)
model.classifier[1] = torch.nn.Linear(model.last_channel, 2)
model.load_state_dict(torch.load('mobilenet_v2_best.pth'))
model.eval()

# Prepare transform
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# Predict
def predict_bot(image_path):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_tensor = transform(img).unsqueeze(0)
    
    with torch.no_grad():
        output = model(img_tensor)
        probs = torch.softmax(output, dim=1)
        pred = torch.argmax(probs, dim=1).item()
    
    bot_prob = probs[0][0].item()
    is_bot = pred == 0
    
    return {
        'is_bot': is_bot,
        'bot_probability': bot_prob,
        'confidence': probs[0][pred].item()
    }

# Example usage
result = predict_bot('path/to/avatar.png')
print(f"Bot: {result['is_bot']}, Probability: {result['bot_probability']:.2%}")
```

## Alternative: Keep Using Random Forest

The Random Forest model already trained on your VPS is at:
```
/root/youtube-bot-dataset/models/simple_avatar_classifier.pkl
```

It achieves 73.5% bot recall with instant inference. Good enough for a first iteration!

## Next Steps

1. Train on Colab for best results
2. Compare both models (Random Forest vs CNN)
3. Create ensemble: Use both models and combine predictions
4. Integrate into your bot detection pipeline

## Troubleshooting

**Out of Memory on Colab**: Reduce `BATCH_SIZE` from 64 to 32 in the notebook

**Upload Too Slow**: Compress dataset more: `tar -czf dataset.tar.gz dataset/`

**Need More Epochs**: Change `NUM_EPOCHS` from 15 to 20-25 in the notebook
