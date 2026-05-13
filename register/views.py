import cv2
import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.shortcuts import render, redirect

from models.processing import preprocess_face, estimate_pose_and_quality
from .forms import UserForm
from .models import FaceImage


MIN_IMAGES = 2
MAX_IMAGES = 5


def register(request):
    return render(request, 'register/register.html')


def upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        count = len(files)

        if count < MIN_IMAGES or count > MAX_IMAGES:
            return render(request, 'register/register-upload.html', {
                'error': f'Can {MIN_IMAGES}-{MAX_IMAGES} anh, nhan duoc {count}.'
            })

        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        temp_key = uuid4().hex
        temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key
        raw_dir = temp_dir / 'raw'
        processed_dir = temp_dir / 'processed'
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        # Save raw files to temp
        raw_paths = []
        for image in files:
            extension = Path(image.name).suffix.lower()
            if extension not in allowed_extensions or not image.content_type.startswith('image/'):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return render(request, 'register/register-upload.html', {
                    'error': 'Only support JPG, PNG or WEBP.'
                })

            filename = f'{uuid4().hex}{extension}'
            raw_path = raw_dir / filename
            with raw_path.open('wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)
            raw_paths.append(raw_path)

        # Process and filter accepted images
        accepted = []
        for raw_path in raw_paths:
            try:
                aligned, face_info = preprocess_face(str(raw_path))
                result = estimate_pose_and_quality(aligned, face_info)

                if not result['reject']:
                    proc_filename = raw_path.stem + '_processed.jpg'
                    proc_path = processed_dir / proc_filename
                    cv2.imwrite(str(proc_path), cv2.cvtColor(aligned, cv2.COLOR_RGB2BGR))
                    accepted.append({'raw': raw_path.name, 'processed': proc_filename})

            except ValueError:
                pass  # No face detected in this image

        if len(accepted) < MIN_IMAGES:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return render(request, 'register/register-upload.html', {
                'error': f'Chi {len(accepted)}/{len(raw_paths)} anh dat yeu cau. Vui long chon lai anh ro hon.'
            })

        request.session['temp_upload_key'] = temp_key
        request.session['accepted_images'] = accepted
        return redirect('register-info')

    return render(request, 'register/register-upload.html')


def register_info(request):
    temp_key = request.session.get('temp_upload_key')
    accepted = request.session.get('accepted_images', [])

    if not temp_key or not accepted:
        return redirect('register-upload')

    if request.method == 'POST':
        form = UserForm(request.POST)

        if form.is_valid():
            user = form.save()

            temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key

            for img_info in accepted:
                raw_path = temp_dir / 'raw' / img_info['raw']
                proc_path = temp_dir / 'processed' / img_info['processed']

                face = FaceImage(user=user)
                with raw_path.open('rb') as rf, proc_path.open('rb') as pf:
                    face.raw_image.save(img_info['raw'], File(rf), save=False)
                    face.processed_image.save(img_info['processed'], File(pf), save=False)
                face.save()

            shutil.rmtree(temp_dir, ignore_errors=True)
            del request.session['temp_upload_key']
            del request.session['accepted_images']
            return redirect('home')

    else:
        form = UserForm()

    return render(request, 'register/register-info.html', {'form': form})


def camera(request):
    return render(request, 'register/register-camera.html')
