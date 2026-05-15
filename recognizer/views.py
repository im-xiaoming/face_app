from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .recognition_core.service import recognize_frame

# Create your views here.
def recognizer(request):
    return render(request, 'recognizer/recognition.html')


@csrf_exempt
@require_POST
def recognition_api(request):
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({
            'status': 'error',
            'message': 'Thieu frame camera.',
        }, status=400)

    return JsonResponse(recognize_frame(image))
