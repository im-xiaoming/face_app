from django.contrib import admin
from .models import UserModel, FaceImage, UserEmbedding

# Register your models here.
@admin.register(UserModel)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'dob']
    list_filter = ['id', 'name']
    search_fields = ['name', 'email']
    
    
@admin.register(FaceImage)
class FaceImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'raw_image', 'processed_image']
    

@admin.register(UserEmbedding)
class UserEmbeddingModel(admin.ModelAdmin):
    list_display = ['get_user_id', 'embed_id']
    
    def get_user_id(self, obj):
        return obj.user.id
    
    get_user_id.short_description = 'User ID'