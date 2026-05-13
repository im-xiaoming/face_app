from django.contrib import admin
from .models import UserModel, FaceImage

# Register your models here.
@admin.register(UserModel)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'dob']
    list_filter = ['id', 'name']
    search_fields = ['name', 'email']
    
    
@admin.register(FaceImage)
class FaceImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'image']