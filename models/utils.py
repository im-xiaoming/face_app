from concurrent.futures import ThreadPoolExecutor
from PIL import Image

def load_image(path):
    try:
        img = Image.open(path).convert('RGB')
        img.load()
        return img
    except Exception as e:
        print(f'Error {path}: {e}')
        return None


def load_images(image_paths, max_workers=8):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        images = list(executor.map(load_image, image_paths))

    # bỏ ảnh lỗi
    images = [img for img in images if img is not None]

    return images