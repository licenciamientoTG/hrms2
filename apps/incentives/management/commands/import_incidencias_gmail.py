"""
Management command para importar incidencias/correcciones de corte desde Gmail.

Uso:
  # Importar el Excel más reciente (todas las semanas nuevas)
  python manage.py import_incidencias_gmail

  # Importar solo una semana específica del Excel
  python manage.py import_incidencias_gmail --semana 2026-09-27

  # Forzar sobreescritura de semanas que ya existen
  python manage.py import_incidencias_gmail --forzar

  # Solo importar semanas a partir de cierta fecha (útil la primera vez)
  python manage.py import_incidencias_gmail --desde 2026-09-01

  # Usar remitente alternativo
  python manage.py import_incidencias_gmail --remitente otro@totalgas.com
"""

from datetime import date
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.incentives.gmail_incidencias_service import importar_incidencias
from apps.incentives.models import IncidenciaUpload, IncidenciaRegistro
from apps.incentives.constants import STATION_TEAMS, EXCEL_CODE_TO_TEAM_KEY

_ACENTO_MAP = str.maketrans('áéíóúüÁÉÍÓÚÜ', 'aeiouuAEIOUU')


def _sin_acentos(s: str) -> str:
    return s.translate(_ACENTO_MAP).upper()


def _resolver_team_key(estacion_raw: str) -> str | None:
    """
    Intenta mapear el valor de la columna Estacion al team_key del sistema.
    El Excel usa tanto códigos numéricos (1242, 6947) como nombres en mayúsculas
    (JARUDO, SATELITE, SANTIAGO, etc.).
    """
    s = estacion_raw.strip()
    s_norm = _sin_acentos(s)

    # Código numérico → buscar en EXCEL_CODE_TO_TEAM_KEY primero
    if s.isdigit():
        if s in EXCEL_CODE_TO_TEAM_KEY:
            return EXCEL_CODE_TO_TEAM_KEY[s]
        if s in STATION_TEAMS:
            return s
        return None

    # Coincidencia directa con claves de STATION_TEAMS (sin acentos)
    for key in STATION_TEAMS:
        if _sin_acentos(key) == s_norm:
            return key

    # Coincidencia por nombre/valor de STATION_TEAMS (sin acentos)
    for key, nombre in STATION_TEAMS.items():
        if _sin_acentos(nombre) == s_norm:
            return key

    return None


class Command(BaseCommand):
    help = 'Importa incidencias/correcciones de corte desde el Excel adjunto en Gmail'

    def add_arguments(self, parser):
        parser.add_argument(
            '--semana',
            type=str,
            default=None,
            help='Semana a importar en formato YYYY-MM-DD (por defecto: la del correo más reciente)',
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            default=False,
            help='Sobreescribir semanas que ya existen en la base de datos',
        )
        parser.add_argument(
            '--desde',
            type=str,
            default=None,
            help='Solo importar semanas a partir de esta fecha YYYY-MM-DD (útil la primera vez)',
        )
        parser.add_argument(
            '--remitente',
            type=str,
            default=None,
            help='Correo del remitente alternativo',
        )

    def handle(self, *args, **options):
        semana_filtro = None
        if options['semana']:
            try:
                semana_filtro = date.fromisoformat(options['semana'])
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    'Formato de semana inválido. Usa YYYY-MM-DD (ej. 2026-09-27)'
                ))
                return

        desde_filtro = None
        if options['desde']:
            try:
                desde_filtro = date.fromisoformat(options['desde'])
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    'Formato de --desde inválido. Usa YYYY-MM-DD (ej. 2026-09-01)'
                ))
                return

        self.stdout.write('Buscando correo de incidencias en Gmail...')

        resultado = importar_incidencias(
            semana=semana_filtro,
            remitente=options.get('remitente'),
        )

        if resultado['error']:
            self.stderr.write(self.style.ERROR(f'Error: {resultado["error"]}'))
            return

        semanas = resultado['semanas']
        msg_id = resultado.get('msg_id', '')
        self.stdout.write(f'Correo encontrado (msg_id: {msg_id}). Semanas en el Excel: {len(semanas)}')

        # Si se filtró por semana específica, ignorar el resto
        if semana_filtro and semana_filtro not in semanas:
            self.stdout.write(self.style.WARNING(
                f'La semana {semana_filtro} no está en el Excel. '
                f'Semanas disponibles: {sorted(semanas.keys())}'
            ))
            return

        if semana_filtro:
            semanas_a_importar = {semana_filtro: semanas[semana_filtro]}
        elif desde_filtro:
            semanas_a_importar = {f: r for f, r in semanas.items() if f >= desde_filtro}
            self.stdout.write(
                f'Filtrando desde {desde_filtro}: {len(semanas_a_importar)} de {len(semanas)} semanas'
            )
        else:
            semanas_a_importar = semanas

        total_guardados = 0
        total_sin_match = 0

        for fecha_semana, registros in sorted(semanas_a_importar.items()):
            # Verificar si ya existe
            ya_existe = IncidenciaUpload.objects.filter(semana=fecha_semana).exists()
            if ya_existe and not options['forzar']:
                self.stdout.write(self.style.WARNING(
                    f'  Semana {fecha_semana} ya importada — omitiendo '
                    f'(usa --forzar para sobreescribir)'
                ))
                continue

            # Borrar registros previos si se fuerza
            if ya_existe:
                IncidenciaUpload.objects.filter(semana=fecha_semana).delete()

            upload = IncidenciaUpload.objects.create(
                semana=fecha_semana,
                total_registros=0,
                gmail_msg_id=msg_id,
            )

            guardados = 0
            sin_match = 0
            bulk = []

            for reg in registros:
                team_key = _resolver_team_key(reg['estacion_key'])
                if not team_key:
                    self.stdout.write(
                        f'    Sin match: estación "{reg["estacion_key"]}"'
                    )
                    sin_match += 1
                    # Guardar igual con la clave original para no perder datos
                    team_key = reg['estacion_key']

                bulk.append(IncidenciaRegistro(
                    upload=upload,
                    problema=reg['problema'],
                    fecha=reg['fecha'],
                    estacion_key=team_key,
                    turno=reg['turno'],
                    tipo_incidencia=reg['tipo_incidencia'],
                    sub_detalle=reg['sub_detalle'],
                    detalle=reg['detalle'],
                    semana=reg['semana'],
                    nombre_estacion=reg['nombre_estacion'],
                    mes=reg['mes'],
                    zona=reg['zona'],
                ))
                guardados += 1

            IncidenciaRegistro.objects.bulk_create(bulk)
            upload.total_registros = guardados
            upload.save(update_fields=['total_registros'])

            self.stdout.write(self.style.SUCCESS(
                f'  Semana {fecha_semana}: {guardados} registros guardados'
                + (f', {sin_match} sin match de estación' if sin_match else '')
            ))
            total_guardados += guardados
            total_sin_match += sin_match

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal importado: {total_guardados} registros'
            + (f', {total_sin_match} sin match' if total_sin_match else '')
        ))
