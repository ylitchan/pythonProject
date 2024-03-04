from django.db import models

# Create your models here.
class Image(models.Model):
    file_key = models.TextField()
    created_time = models.DateTimeField(auto_now_add=True)
