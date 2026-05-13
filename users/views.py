from django.shortcuts import render
from register.models import UserModel

# Create your views here.
def list_users(request):
    users = UserModel.objects.all()
    return render(request, 'users/users.html', {'users': users})