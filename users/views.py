from django.shortcuts import render

# Create your views here.
def list_users(request):
    return render(request, 'users/users.html')