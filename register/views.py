from django.shortcuts import render

# Create your views here.
def register(request):
    return render(request, 'register/register.html')


def upload(request):
    return render(request, 'register/register-upload.html')