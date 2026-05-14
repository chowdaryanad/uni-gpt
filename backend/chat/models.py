from django.db import models


# Create your models here.
class ChatHistory(models.Model):
    user_query = models.TextField()
    bot_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)