"""
Management command para importar el presupuesto mensual de ventas desde Gmail.

Uso:
  # Importar el mes actual
  python manage.py import_presupuesto_gmail

  # Importar un mes específico
  python manage.py import_presupuesto_gmail --mes 2026-08

  # Forzar sobreescritura si ya existe el presupuesto
  python manage.py import_presupuesto_gmail --mes 2026-08 --forzar

  # Importar cuando el correo lo mandó otra persona (caso excepcional)
  python manage.py import_presupuesto_gmail --mes 2026-07 --remitente alejandro.martinez@totalgas.com
"""

from datetime import date
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.incentives.gmail_budget_service import importar_presupuesto
from apps.incentives.models import PresupuestoVenta
from apps.incentives.constants import STATION_TEAMS, EXCEL_CODE_TO_TEAM_KEY


class Command(BaseCommand):
    help = 'Importa el presupuesto mensual de ventas desde el correo de Gmail'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mes',
            type=str,
            default=None,
            help='Mes a importar en formato YYYY-MM (por defecto: mes actual)',
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            default=False,
            help='Sobreescribir si ya existe presupuesto para ese mes',
        )
        parser.add_argument(
            '--remitente',
            type=str,
            default=None,
            help='Correo del remitente alternativo (por defecto: gerente.operaciones@totalgas.com)',
        )

    def handle(self, *args, **options):
        # --- Determinar el mes ---
        if options['mes']:
            try:
                año, mes_num = options['mes'].split('-')
                mes = date(int(año), int(mes_num), 1)
            except (ValueError, AttributeError):
                self.stderr.write(self.style.ERROR('Formato de mes inválido. Usa YYYY-MM (ej. 2026-08)'))
                return
        else:
            hoy = timezone.now().date()
            mes = date(hoy.year, hoy.month, 1)

        self.stdout.write(f'Importando presupuesto para: {mes.strftime("%B %Y")}')

        # --- Verificar si ya existe ---
        ya_existe = PresupuestoVenta.objects.filter(mes=mes).exists()
        if ya_existe and not options['forzar']:
            self.stdout.write(
                self.style.WARNING(
                    f'Ya existe presupuesto para {mes.strftime("%B %Y")}. '
                    f'Usa --forzar para sobreescribir.'
                )
            )
            return

        # --- Obtener datos de Gmail ---
        resultado = importar_presupuesto(mes, remitente=options.get('remitente'))

        if resultado['error']:
            self.stderr.write(self.style.ERROR(f'Error: {resultado["error"]}'))
            return

        filas = resultado['filas']
        self.stdout.write(f'Correo encontrado. Filas en tabla: {len(filas)}')

        # --- Guardar en base de datos ---
        guardados = 0
        sin_match = 0

        for fila in filas:
            codigo = fila['codigo']

            # Resolver team_key
            team_key = None
            if codigo in STATION_TEAMS:
                team_key = codigo
            elif codigo in EXCEL_CODE_TO_TEAM_KEY:
                team_key = EXCEL_CODE_TO_TEAM_KEY[codigo]

            if not team_key:
                self.stdout.write(f'  Sin match: código {codigo}')
                sin_match += 1
                continue

            PresupuestoVenta.objects.update_or_create(
                team_key=team_key,
                mes=mes,
                defaults={
                    'maxima':         fila['maxima'],
                    'gasolina_super': fila['gasolina_super'],
                    'diesel':         fila['diesel'],
                    'total':          fila['total'],
                    'subido_por':     None,
                }
            )
            guardados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Presupuesto importado: {guardados} estaciones guardadas, {sin_match} sin match.'
        ))
        if resultado['msg_id']:
            self.stdout.write(f'Gmail message ID: {resultado["msg_id"]}')
