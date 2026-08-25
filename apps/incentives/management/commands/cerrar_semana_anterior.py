from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.incentives.models import SemanaCerrada


class Command(BaseCommand):
    help = 'Cierra automáticamente la semana anterior si aún no fue cerrada.'

    def handle(self, *args, **options):
        today = date.today()
        # Lunes de la semana pasada
        lunes_semana_pasada = today - timedelta(days=today.weekday()) - timedelta(weeks=1)

        _, created = SemanaCerrada.objects.get_or_create(
            week_start=lunes_semana_pasada,
            defaults={'cerrada_por': None},
        )
        if created:
            self.stdout.write(f'Semana {lunes_semana_pasada} cerrada automáticamente.')
        else:
            self.stdout.write(f'Semana {lunes_semana_pasada} ya estaba cerrada.')
