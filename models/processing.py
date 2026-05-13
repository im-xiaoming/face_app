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


def _get_model():
    if _cache:
        return _cache['app'], _cache['model'], _cache['transform']
    
    app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(device)

    # transform
    transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])

    # model
    model = get_model('ir_50', device)
    load_weight(model, Path(settings.BASE_DIR) / 'checkpoints' / 'ir_50.pth')
    model.to(device)

    _cache['app'] = app
    _cache['model'] = model
    _cache['transform'] = transform
    
    return app, model, transform



def preprocess_face(image_path: str) -> tuple[np.ndarray, dict]:
    
    app, model, transform = _get_model()
    
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

    return aligned, face_info


def estimate_pose_and_quality(aligned_face: np.ndarray, face_info) -> dict:
    results_dict = {
        "yaw"            : None,
        "pitch"          : None,
        "roll"           : None,
        "quality"        : None,
        "reject"         : False,
        "reject_reason"  : None,
    }

    # ── 1. Quality check ──────────────────────────────────────
    gray = cv2.cvtColor(aligned_face, cv2.COLOR_RGB2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = gray.mean()

    if blur_score < 20.0:
        results_dict["reject"] = True
        results_dict["reject_reason"] = f"Quá mờ (blur={blur_score:.1f})"
        return results_dict

    if brightness < 30 or brightness > 220:
        results_dict["reject"] = True
        results_dict["reject_reason"] = f"Ánh sáng không đạt (brightness={brightness:.1f})"
        return results_dict

    quality = min(blur_score / 200.0, 1.0) * (1 - abs(brightness - 127) / 127)
    results_dict["quality"] = round(quality, 4)

    pose = face_info.pose  # buffalo_sc trả về [pitch, yaw, roll]
    pitch = float(pose[0])
    yaw   = float(pose[1])
    roll  = float(pose[2])

    results_dict["yaw"]   = round(yaw, 2)
    results_dict["pitch"] = round(pitch, 2)
    results_dict["roll"]  = round(roll, 2)

    return results_dict


