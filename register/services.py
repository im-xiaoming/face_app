import cv2
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files import File

from models.processing import preprocess_face, estimate_pose_and_quality
from users.models import FaceImage


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def make_temp_dirs(temp_key: str) -> tuple[Path, Path, Path]:
    """Tạo thư mục temp/raw/processed. Trả về (temp_dir, raw_dir, processed_dir)."""
    temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key
    raw_dir = temp_dir / 'raw'
    processed_dir = temp_dir / 'processed'
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir, raw_dir, processed_dir


def _save_single_file(image, raw_dir: Path) -> Path:
    """Validate và lưu một file vào raw_dir. Raise ValueError nếu không hợp lệ."""
    extension = Path(image.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or not image.content_type.startswith('image/'):
        raise ValueError('Only support JPG, PNG or WEBP.')

    raw_path = raw_dir / f'{uuid4().hex}{extension}'
    with raw_path.open('wb+') as f:
        for chunk in image.chunks():
            f.write(chunk)
    return raw_path


def save_raw_files(files, raw_dir: Path) -> list[Path]:
    """Lưu song song các file upload vào raw_dir. Raise ValueError nếu có file không hợp lệ."""
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_save_single_file, img, raw_dir) for img in files]
        return [f.result() for f in futures]


def _process_single(raw_path: Path, processed_dir: Path) -> dict | None:
    """Xử lý một ảnh qua pipeline. Trả về dict nếu đạt, None nếu bị reject hoặc không có face."""
    try:
        aligned, face_info = preprocess_face(str(raw_path))
        result = estimate_pose_and_quality(aligned, face_info)

        if result['reject']:
            return None

        proc_filename = raw_path.stem + '_processed.jpg'
        cv2.imwrite(str(processed_dir / proc_filename), cv2.cvtColor(aligned, cv2.COLOR_RGB2BGR))
        return {'raw': raw_path.name, 'processed': proc_filename}

    except ValueError:
        return None


def process_images(raw_paths: list[Path], processed_dir: Path) -> list[dict]:
    """Xử lý song song tất cả ảnh. Trả về list ảnh đạt yêu cầu."""
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_process_single, p, processed_dir) for p in raw_paths]
        results = [f.result() for f in futures]
    return [r for r in results if r is not None]


def save_face_images(user, accepted: list[dict], temp_dir: Path) -> None:
    """Tạo FaceImage cho từng ảnh đạt, lưu cả raw lẫn processed vào DB và storage."""
    for img_info in accepted:
        raw_path = temp_dir / 'raw' / img_info['raw']
        proc_path = temp_dir / 'processed' / img_info['processed']

        face = FaceImage(user=user)
        with raw_path.open('rb') as rf, proc_path.open('rb') as pf:
            face.raw_image.save(img_info['raw'], File(rf), save=False)
            face.processed_image.save(img_info['processed'], File(pf), save=False)
        face.save()

    shutil.rmtree(temp_dir, ignore_errors=True)
