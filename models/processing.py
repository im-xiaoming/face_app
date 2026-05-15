import cv2
from insightface.app import FaceAnalysis
from insightface.utils import face_align
import numpy as np
import torch
from torchvision import transforms
from xiaoying.utils import get_model, load_weight
from django.conf import settings
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

_cache = {}


MIN_BLUR_SCORE = 50.0
MIN_BRIGHTNESS = 50.0
MAX_BRIGHTNESS = 215.0
MIN_DET_SCORE = 0.65
MIN_FACE_AREA_RATIO = 0.04

POSE_LIMITS = {
    'front': {
        'yaw': (-14.0, 14.0),
        'pitch': (-18.0, 18.0),
        'roll': (-15.0, 15.0),
    },
    'left': {
        'yaw': (8.0, 55.0),
        'pitch': (-22.0, 22.0),
        'roll': (-18.0, 18.0),
    },
    'right': {
        'yaw': (-55.0, -8.0),
        'pitch': (-22.0, 22.0),
        'roll': (-18.0, 18.0),
    },
}


def _get_model():
    if _cache:
        return _cache['app'], _cache['model'], _cache['transform'], _cache['device']

    app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(device)

    transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])

    model = get_model('ir_50', device)
    load_weight(model, Path(settings.BASE_DIR) / 'checkpoints' / 'ir_50.pth')
    model.to(device)

    _cache['app'] = app
    _cache['model'] = model
    _cache['transform'] = transform
    _cache['device'] = device

    return app, model, transform, device



def preprocess_face(image_path: str) -> tuple[np.ndarray, dict]:

    app, _, _, _ = _get_model()

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    faces = app.get(img_rgb)
    if len(faces) == 0:
        raise ValueError("Không phát hiện khuôn mặt nào.")

    img_area = img_rgb.shape[0] * img_rgb.shape[1]

    def combined_score(f):
        b = f.bbox
        area = (b[2] - b[0]) * (b[3] - b[1])
        area_score = area / img_area
        conf_score = float(f.det_score)
        return 0.7 * area_score + 0.3 * conf_score

    face_info = sorted(faces, key=combined_score, reverse=True)[0]
    aligned = face_align.norm_crop(img_rgb, landmark=face_info.kps, image_size=112)
    face_info._img_area = img_area

    return aligned, face_info


def estimate_pose_and_quality(aligned_face: np.ndarray, face_info, expected_pose: str | None = None) -> dict:
    results_dict = {
        "yaw"            : None,
        "pitch"          : None,
        "roll"           : None,
        "quality"        : None,
        "det_score"      : None,
        "face_area_ratio": None,
        "reject"         : False,
        "reject_reason"  : None,
    }

    det_score = float(getattr(face_info, 'det_score', 0.0))
    results_dict["det_score"] = round(det_score, 4)
    if det_score < MIN_DET_SCORE:
        results_dict["reject"] = True
        results_dict["reject_reason"] = f"Do tin cay phat hien thap (det_score={det_score:.2f})"
        return results_dict

    img_area = float(getattr(face_info, '_img_area', 0.0))
    if img_area > 0:
        b = face_info.bbox
        face_area = float((b[2] - b[0]) * (b[3] - b[1]))
        face_area_ratio = face_area / img_area
        results_dict["face_area_ratio"] = round(face_area_ratio, 4)
        if face_area_ratio < MIN_FACE_AREA_RATIO:
            results_dict["reject"] = True
            results_dict["reject_reason"] = f"Khuon mat qua nho (ratio={face_area_ratio:.3f})"
            return results_dict

    gray = cv2.cvtColor(aligned_face, cv2.COLOR_RGB2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    if blur_score < MIN_BLUR_SCORE:
        results_dict["reject"] = True
        results_dict["reject_reason"] = f"Anh qua mo (blur={blur_score:.1f})"
        return results_dict

    if brightness < MIN_BRIGHTNESS or brightness > MAX_BRIGHTNESS:
        results_dict["reject"] = True
        results_dict["reject_reason"] = f"Anh sang khong dat (brightness={brightness:.1f})"
        return results_dict

    quality = min(blur_score / 200.0, 1.0) * (1 - abs(brightness - 127) / 127)
    results_dict["quality"] = round(quality, 4)

    pose = face_info.pose
    pitch = float(pose[0])
    yaw   = float(pose[1])
    roll  = float(pose[2])

    results_dict["yaw"]   = round(yaw, 2)
    results_dict["pitch"] = round(pitch, 2)
    results_dict["roll"]  = round(roll, 2)

    if expected_pose and expected_pose in POSE_LIMITS:
        limits = POSE_LIMITS[expected_pose]
        if not (limits['yaw'][0] <= yaw <= limits['yaw'][1]):
            results_dict["reject"] = True
            results_dict["reject_reason"] = (
                f"Yaw khong khop pose '{expected_pose}' (yaw={yaw:.1f})"
            )
            return results_dict
        if not (limits['pitch'][0] <= pitch <= limits['pitch'][1]):
            results_dict["reject"] = True
            results_dict["reject_reason"] = (
                f"Pitch ngoai gioi han pose '{expected_pose}' (pitch={pitch:.1f})"
            )
            return results_dict
        if not (limits['roll'][0] <= roll <= limits['roll'][1]):
            results_dict["reject"] = True
            results_dict["reject_reason"] = (
                f"Roll ngoai gioi han pose '{expected_pose}' (roll={roll:.1f})"
            )
            return results_dict

    return results_dict
