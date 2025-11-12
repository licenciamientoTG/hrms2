# apps/news/management/commands/publish_due_news.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.news.models import News
from apps.news.services import publish_news_if_due

class Command(BaseCommand):
    help = "Publica y envía correo de noticias cuyo publish_at ya venció."

    def handle(self, *args, **options):
        now = timezone.now()
        # Candidatas: no publicadas y con publish_at vencido
        qs = News.objects.filter(published_at__isnull=True, publish_at__isnull=False, publish_at__lte=now)
        total = 0
        for n in qs:
            if publish_news_if_due(n):
                total += 1
                self.stdout.write(self.style.SUCCESS(f"Publicado y enviado: {n.id} | {n.title}"))
        self.stdout.write(self.style.NOTICE(f"Total procesadas: {total}"))
