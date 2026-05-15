from django.urls import path
from .import views

urlpatterns = [
    path('recognition/', views.recognizer, name='recognition'),
    path('recognition/api/', views.recognition_api, name='recognition-api'),
]
