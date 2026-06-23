from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)
    accepted_terms = models.BooleanField(default=False)
    accepted_checador_policy = models.BooleanField(default=False)
    accepted_checador_policy_at = models.DateTimeField(null=True, blank=True)
