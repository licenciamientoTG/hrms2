from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class SessionEvent(models.Model):
    LOGIN  = "login"
    LOGOUT = "logout"
    EVENT_CHOICES = [(LOGIN, "Login"), (LOGOUT, "Logout")]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event      = models.CharField(max_length=10, choices=EVENT_CHOICES)
    ts         = models.DateTimeField(auto_now_add=True)  # timestamp del evento
    ip         = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["user", "ts"]),
            models.Index(fields=["event", "ts"]),
        ]

    def __str__(self):
        return f"{self.user} {self.event} @ {self.ts:%Y-%m-%d %H:%M}"
