import json
import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.shortcuts import render, redirect

from .forms import UserForm
from .services import make_temp_dirs, save_raw_files, process_images, save_face_images, schedule_embedding_extraction


MIN_IMAGES = 2
MAX_IMAGES = 5
CAMERA_POSES = ['front', 'left', 'right']


def register(request):
    return render(request, 'register/register.html')


def upload(request):
    if request.method != 'POST':
        return render(request, 'register/register-upload.html')

    files = request.FILES.getlist('images')
    if not (MIN_IMAGES <= len(files) <= MAX_IMAGES):
        return render(request, 'register/register-upload.html', {
            'error': f'Can {MIN_IMAGES}-{MAX_IMAGES} anh, nhan duoc {len(files)}.'
        })

    temp_key = uuid4().hex
    temp_dir, raw_dir, processed_dir = make_temp_dirs(temp_key)

    try:
        raw_paths = save_raw_files(files, raw_dir)
    except ValueError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return render(request, 'register/register-upload.html', {'error': str(e)})

    accepted = process_images(raw_paths, processed_dir)

    if len(accepted) < MIN_IMAGES:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return render(request, 'register/register-upload.html', {
            'error': f'Chi {len(accepted)}/{len(raw_paths)} anh dat yeu cau. Vui long chon lai anh ro hon.'
        })

    request.session['temp_upload_key'] = temp_key
    request.session['accepted_images'] = accepted
    request.session['register_source'] = 'upload'
    return redirect('register-info')


def register_info(request):
    temp_key = request.session.get('temp_upload_key')
    accepted = request.session.get('accepted_images', [])
    source = request.session.get('register_source', 'upload')

    if not temp_key or not accepted:
        return redirect('register-upload')

    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save()
            temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key
            face_images = save_face_images(user, accepted, temp_dir)
            schedule_embedding_extraction(user, face_images)
            del request.session['temp_upload_key']
            del request.session['accepted_images']
            request.session.pop('register_source', None)
            return redirect('home')
    else:
        form = UserForm()

    return render(request, 'register/register-info.html', {'form': form, 'source': source})


def camera(request):
    if request.method != 'POST':
        return render(request, 'register/register-camera.html')

    files = request.FILES.getlist('images')
    try:
        poses = json.loads(request.POST.get('poses', '[]'))
    except json.JSONDecodeError:
        poses = []

    if len(files) != len(CAMERA_POSES) or poses != CAMERA_POSES:
        return render(request, 'register/register-camera.html', {
            'error': 'Can chup du 3 anh: nhin thang, quay trai, quay phai.'
        })

    temp_key = uuid4().hex
    temp_dir, raw_dir, processed_dir = make_temp_dirs(temp_key)

    try:
        raw_paths = save_raw_files(files, raw_dir)
    except ValueError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return render(request, 'register/register-camera.html', {'error': str(e)})

    accepted = process_images(raw_paths, processed_dir, poses=poses)

    if len(accepted) != len(CAMERA_POSES):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return render(request, 'register/register-camera.html', {
            'error': f'Chi {len(accepted)}/3 anh dat yeu cau. Vui long chup lai voi anh sang tot hon.'
        })

    request.session['temp_upload_key'] = temp_key
    request.session['accepted_images'] = accepted
    request.session['register_source'] = 'camera'
    return redirect('register-info')
