from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.recognitions.models import Recognition
from apps.recognitions.services import publish_recognition_if_due

class Command(BaseCommand):
    help = "Publica comunicado cuyo publish_at ya venció"

    def handle(self, *args, **kwargs):
        qs = Recognition.objects.filter(published_at__isnull=True, publish_at__lte=timezone.now())
        count = 0
        for rec in qs:
            published, _ = publish_recognition_if_due(rec)
            if published:
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Publicados: {count}"))