import torch
from .processing import _get_model
from .utils import load_images

def inference(files):
    _, model, transform, device = _get_model()
    images = load_images(files)
    images = transform(images)
    images = torch.stack(images)
    
    model.eval()
    with torch.no_grad():
        embeddings, _ = model(images.to(device))
        
    return embeddings