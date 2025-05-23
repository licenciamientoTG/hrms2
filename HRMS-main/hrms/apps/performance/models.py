from django.db import models
from django.contrib.auth.models import User

class PerformanceReview(models.Model):
    RATING_CHOICES = [
        (1, 'Poor'),
        (2, 'Fair'),
        (3, 'Good'),
        (4, 'Very Good'),
        (5, 'Excellent'),
    ]

    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comments = models.TextField()
    date_reviewed = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.employee.username} by {self.reviewer.username}"
