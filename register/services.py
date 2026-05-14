import cv2
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files import File

from models.processing import preprocess_face, estimate_pose_and_quality
from users.models import FaceImage, FacePose, UserEmbedding

logger = logging.getLogger(__name__)


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
VALID_POSES = {FacePose.FRONT, FacePose.LEFT, FacePose.RIGHT, FacePose.UNKNOWN}


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


def normalize_pose(value: str | None) -> str:
    if value in VALID_POSES:
        return value
    return FacePose.UNKNOWN


def classify_pose(yaw: float | None) -> str:
    if yaw is None:
        return FacePose.UNKNOWN
    if yaw < -12:
        return FacePose.LEFT
    if yaw > 12:
        return FacePose.RIGHT
    return FacePose.FRONT


def _process_single(raw_path: Path, processed_dir: Path, pose: str | None = None) -> dict | None:
    """Xử lý một ảnh qua pipeline. Trả về dict nếu đạt, None nếu bị reject hoặc không có face."""
    try:
        aligned, face_info = preprocess_face(str(raw_path))
        expected = pose if pose in {FacePose.FRONT, FacePose.LEFT, FacePose.RIGHT} else None
        result = estimate_pose_and_quality(aligned, face_info, expected_pose=expected)

        if result['reject']:
            logger.info("Rejected %s: %s", raw_path.name, result.get('reject_reason'))
            return None

        proc_filename = raw_path.stem + '_processed.jpg'
        cv2.imwrite(str(processed_dir / proc_filename), cv2.cvtColor(aligned, cv2.COLOR_RGB2BGR))
        return {
            'raw': raw_path.name,
            'processed': proc_filename,
            'pose': normalize_pose(pose) if pose else classify_pose(result.get('yaw')),
        }

    except ValueError:
        return None


def process_images(raw_paths: list[Path], processed_dir: Path, poses: list[str] | None = None) -> list[dict]:
    """Xử lý song song tất cả ảnh. Trả về list ảnh đạt yêu cầu."""
    if poses is None:
        poses = [None] * len(raw_paths)

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(_process_single, path, processed_dir, pose)
            for path, pose in zip(raw_paths, poses)
        ]
        results = [f.result() for f in futures]
    return [r for r in results if r is not None]


def save_face_images(user, accepted: list[dict], temp_dir: Path) -> list[FaceImage]:
    """Tạo FaceImage cho từng ảnh đạt, lưu cả raw lẫn processed vào DB và storage."""
    face_images = []
    for img_info in accepted:
        raw_path = temp_dir / 'raw' / img_info['raw']
        proc_path = temp_dir / 'processed' / img_info['processed']

        face = FaceImage(user=user)
        face.pose = normalize_pose(img_info.get('pose'))
        with raw_path.open('rb') as rf, proc_path.open('rb') as pf:
            face.raw_image.save(img_info['raw'], File(rf), save=False)
            face.processed_image.save(img_info['processed'], File(pf), save=False)
        face.save()
        face_images.append(face)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return face_images


def _extract_and_store_embeddings(user, face_images: list[FaceImage]) -> None:
    from models import inference
    from tools import update

    try:
        processed_paths = [fi.processed_image.path for fi in face_images]
        embeddings = inference(processed_paths)

        points = []
        for face_img, embedding in zip(face_images, embeddings):
            UserEmbedding.objects.create(user=user, embed_id=face_img.pk, pose=face_img.pose)
            points.append((
                face_img.pk,
                embedding,
                {'embed_id': face_img.pk, 'user_id': user.pk, 'pose': face_img.pose},
            ))

        update(points)
    except Exception:
        logger.exception("Failed to extract/store embeddings for user %s", user.pk)


def schedule_embedding_extraction(user, face_images: list[FaceImage]) -> None:
    threading.Thread(
        target=_extract_and_store_embeddings,
        args=(user, face_images),
        daemon=True,
    ).start()
