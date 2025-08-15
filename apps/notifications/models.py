from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=140)
    body  = models.TextField(blank=True)
    url   = models.URLField(blank=True)  # opcional
    created_at = models.DateTimeField(auto_now_add=True)
    read_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['user', 'read_at', '-created_at'])]

    @property
    def is_read(self):
        return self.read_at is not None
