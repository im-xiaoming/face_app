import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.shortcuts import render, redirect
from .forms import UserForm
from .models import FaceImage


def register(request):
    return render(request, 'register/register.html')


def upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        count = len(files)

        if count < 2 or count > 5:
            return render(request, 'register/register-upload.html', {
                'error': f'Can 2-5 anh, nhan duoc {count}.'
            })

        # validation
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        temp_key = uuid4().hex
        temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key
        temp_dir.mkdir(parents=True, exist_ok=True)

        for image in files:
            extension = Path(image.name).suffix.lower()
            if extension not in allowed_extensions or not image.content_type.startswith('image/'):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return render(request, 'register/register-upload.html', {
                    'error': 'Only support JPG, PNG or WEBP.'
                })

            filename = f'{uuid4().hex}{extension}'
            with (temp_dir / filename).open('wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)

        request.session['temp_upload_key'] = temp_key
        return redirect('register-info')

    return render(request, 'register/register-upload.html')


def register_info(request):
    temp_key = request.session.get('temp_upload_key')
    if not temp_key:
        return redirect('register-upload')

    if request.method == 'POST':
        form = UserForm(request.POST)

        if form.is_valid():
            user = form.save()

            temp_dir = Path(settings.BASE_DIR) / 'media' / 'temp' / temp_key

            if temp_dir.exists():
                for image_path in sorted(temp_dir.iterdir()):
                    with image_path.open('rb') as f:
                        face = FaceImage(user=user)
                        face.image.save(image_path.name, File(f), save=True)
                shutil.rmtree(temp_dir)

            del request.session['temp_upload_key']
            return redirect('home')
    
    else:
        form = UserForm()

    return render(request, 'register/register-info.html', {'form': form})


def camera(request):
    return render(request, 'register/register-camera.html')
