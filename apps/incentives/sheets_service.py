"""
Servicio para leer datos de ventas de Praxedis y Colosio desde Google Sheets.

Hoja: "Indicadores operativos semanales 2025"
ID:   15mdBC9zHBe2rQmXewzaRf9H93SfJAX1HkDiwjtUDumA

Convención de pestañas: "Semana {semana_iso}-{año_2d}"  ej. "Semana 27-26"
Estructura de cada pestaña (datos desde fila 7):
  Col A: N.o (código)       Col B: Estación
  Ppto Mensual  C=Gas D=Diesel E=Total
  Ppto Semanal  G=Gas H=Diesel I=Total
  Venta Semanal K=Gas L=Dif    M=Diesel N=Dif O=Total P=Dif
"""

import os
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SHEET_ID = '15mdBC9zHBe2rQmXewzaRf9H93SfJAX1HkDiwjtUDumA'
_CREDS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'credentials', 'hrms-incentivos-90f7092e0790.json'
)
_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Substring en col B del Sheet → team_key en STATION_TEAMS
_ESTACION_MAP = {
    'praxedis': 'Praxedis',
    'colosio':  'Colosio',
}

SHEETS_TEAM_KEYS = set(_ESTACION_MAP.values())


def _tab_name(week_start):
    """Calcula el nombre esperado de la pestaña desde la fecha de inicio de semana."""
    iso = week_start.isocalendar()
    return f"Semana {iso[1]}-{iso[0] % 100}"


def _normalizar(nombre):
    """Elimina espacios y convierte a minúsculas para comparación flexible."""
    return nombre.strip().lower().replace(' ', '')


def _get_service():
    creds_path = os.path.abspath(_CREDS_PATH)
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=_SCOPES
    )
    return build('sheets', 'v4', credentials=creds, cache_discovery=False)


def _parse_num(row, idx):
    """Extrae un número de la fila; devuelve 0.0 si falta o no es parseable."""
    try:
        return float(str(row[idx]).replace(',', '').strip()) if len(row) > idx and row[idx] else 0.0
    except (ValueError, TypeError):
        return 0.0


def leer_ventas_praxedis_colosio(week_start):
    """
    Lee la pestaña correspondiente a week_start y devuelve los datos de
    Praxedis y Colosio.

    Returns
    -------
    (ventas_dict, error_str)
      ventas_dict : {team_key: {gas, diesel, total, ppto_gas, ppto_diesel, ppto_total}}
      error_str   : None si OK, mensaje de texto si ocurrió algún error
    """
    try:
        service = _get_service()
        sheets  = service.spreadsheets()

        # 1. Obtener lista de pestañas disponibles
        meta = sheets.get(
            spreadsheetId=SHEET_ID,
            fields='sheets.properties.title',
        ).execute()
        available = {s['properties']['title'] for s in meta.get('sheets', [])}

        # 2. Buscar la pestaña por nombre normalizado (sin importar espacios ni mayúsculas)
        base = _tab_name(week_start)
        # Variantes posibles: "Semana 27-26" y "Semana 27 - 26"
        norm_candidates = {_normalizar(c) for c in [base, base.replace('-', ' - ')]}
        # Mapeo: nombre_normalizado → nombre_real_de_la_pestaña
        norm_to_real = {_normalizar(t): t for t in available}
        tab_name = next(
            (norm_to_real[nc] for nc in norm_candidates if nc in norm_to_real),
            None,
        )

        if tab_name is None:
            recientes = ', '.join(list(available)[:6])
            return {}, f"Pestaña no encontrada: '{base}' — más recientes: {recientes}"

        # 3. Leer filas de datos (desde fila 7)
        rng    = f"'{tab_name}'!A7:O200"
        result = sheets.values().get(spreadsheetId=SHEET_ID, range=rng).execute()
        rows   = result.get('values', [])

        ventas = {}
        for row in rows:
            if len(row) < 2:
                continue
            nombre = row[1].strip().lower() if row[1] else ''
            team_key = next(
                (tk for substr, tk in _ESTACION_MAP.items() if substr in nombre),
                None,
            )
            if team_key is None:
                continue

            ventas[team_key] = {
                'gas':          int(_parse_num(row, 10)),  # K - Venta gas
                'diesel':       int(_parse_num(row, 12)),  # M - Venta diesel
                'total':        int(_parse_num(row, 14)),  # O - Venta total
                'ppto_gas':     int(_parse_num(row, 6)),   # G - Ppto semanal gas
                'ppto_diesel':  int(_parse_num(row, 7)),   # H - Ppto semanal diesel
                'ppto_total':   int(_parse_num(row, 8)),   # I - Ppto semanal total
                'tab': tab_name,
            }

        return ventas, None

    except HttpError as e:
        logger.error("Sheets API HttpError: %s", e)
        return {}, f"Error de Google Sheets API: {e.reason}"
    except Exception as e:
        logger.exception("Error leyendo Google Sheets")
        return {}, str(e)
