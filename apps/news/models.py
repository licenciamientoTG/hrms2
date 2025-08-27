from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator

class NewsTag(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class News(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    cover_image = models.ImageField(
        upload_to='news/covers/',
        null=True, blank=True,
        validators=[FileExtensionValidator(['jpg','jpeg','png','webp','gif'])]
    )
    tags = models.ManyToManyField(NewsTag, blank=True)
    attachments = models.FileField(upload_to='news/attachments/', null=True, blank=True)
    
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=True)
    
    AUDIENCE_CHOICES = [
        ('all', 'Todos los usuarios'),
        ('segment', 'Segmentar'),
    ]
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')

    publish_at = models.DateTimeField(null=True, blank=True)  
    published_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    likes = models.ManyToManyField(User, through='NewsLike', related_name='liked_news', blank=True)

    def __str__(self):
        return self.title

class NewsLike(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='like_set')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='news_like_set')
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('news', 'user')  # 1 like por usuario/noticia