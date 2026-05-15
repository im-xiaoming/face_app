from pathlib import Path

import torch
from django.conf import settings
from PIL import Image
from torchvision import transforms
from xiaoying.utils import get_model, load_weight

_cache = {}


def _load_image(path):
    image = Image.open(path).convert('RGB')
    image.load()
    return image


def _get_embedding_model():
    if _cache:
        return _cache['model'], _cache['transform'], _cache['device']

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = Path(settings.BASE_DIR) / 'checkpoints' / 'ir_50.pth'
    if not checkpoint.exists():
        raise FileNotFoundError(
            f"Missing embedding checkpoint: {checkpoint}. "
            "Add ir_50.pth before using recognition."
        )

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

    model = get_model('ir_50', device)
    load_weight(model, checkpoint)
    model.to(device)
    model.eval()

    _cache['model'] = model
    _cache['transform'] = transform
    _cache['device'] = device

    return model, transform, device


def inference(files):
    model, transform, device = _get_embedding_model()
    images = torch.stack([transform(_load_image(path)) for path in files])

    with torch.no_grad():
        embeddings, _ = model(images.to(device))

    return embeddings
