from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class UserModel(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    dob = models.DateField()

    def __str__(self):
        return self.name


class FaceImage(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='face_images')
    raw_image = models.ImageField(upload_to='registered_faces/raw/')
    processed_image = models.ImageField(upload_to='registered_faces/processed/', blank=True)

    def __str__(self):
        return f'{self.user.name} - {self.pk}'


class UserEmbedding(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='user_embeds')
    embed_id = models.IntegerField(unique=True)
    
    def __str__(self):
        return f'{self.user.name} - {self.pk}'


@receiver(post_delete, sender=FaceImage)
def delete_face_image_file(sender, instance, **kwargs):
    if instance.raw_image:
        instance.raw_image.delete(save=False)
    if instance.processed_image:
        instance.processed_image.delete(save=False)