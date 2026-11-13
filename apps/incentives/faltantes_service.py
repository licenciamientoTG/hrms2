"""
Servicio para leer faltantes de gerentes/subgerentes desde Google Sheets.

Hoja: "Faltantes" (ID: 1HwJWddOpVvegUpolrxpX12M07fsyvhNp5slhO1muCgk)
Pestañas usadas: FALTANTES Z1, FALTANTES Z2, FALTANTES Z3, FALTANTES Z4

Estructura de cada pestaña (encabezado en fila 2, datos desde fila 3):
  Col A: ESTACION   Col B: GERENTE   Col C: IMPORTE FALTANTE
  Col O: CLASIFICACION

Solo se suman clasificaciones: REAL, DESCUENTO VIA NOMINA
"""

import os
import logging
import re

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.incentives.constants import STATION_TEAMS, EXCEL_CODE_TO_TEAM_KEY

logger = logging.getLogger(__name__)

SHEET_ID   = '1HwJWddOpVvegUpolrxpX12M07fsyvhNp5slhO1muCgk'
_CREDS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'credentials', 'hrms-incentivos-90f7092e0790.json'
)
_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

TABS_FALTANTES = [
    'FALTANTES Z1',
    'FALTANTES Z2',
    'FALTANTES Z3',
    'FALTANTES Z4',
]

CLASIFICACIONES_VALIDAS = {'real', 'descuento via nomina'}


def _get_service():
    creds_path = os.path.abspath(_CREDS_PATH)
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=_SCOPES
    )
    return build('sheets', 'v4', credentials=creds, cache_discovery=False)


def _parse_monto(valor):
    """Convierte '$1,234.56' o '1234.56' a float; devuelve 0.0 si no parseable."""
    try:
        limpio = re.sub(r'[^\d.]', '', str(valor).strip())
        return float(limpio) if limpio else 0.0
    except (ValueError, TypeError):
        return 0.0


def _estacion_to_team_key(codigo):
    """Resuelve un código de estación del sheet al team_key del sistema."""
    codigo = str(codigo).strip()
    if codigo in STATION_TEAMS:
        return codigo
    return EXCEL_CODE_TO_TEAM_KEY.get(codigo)


def leer_faltantes_por_estacion():
    """
    Lee las pestañas de faltantes y devuelve totales por estación.

    Returns
    -------
    (totales_dict, error_str)
      totales_dict : {team_key: float}  — suma de IMPORTE FALTANTE filtrado
      error_str    : None si OK, mensaje si ocurrió error
    """
    try:
        service = _get_service()
        sheets  = service.spreadsheets()

        # Obtener nombres reales de pestañas disponibles
        meta = sheets.get(
            spreadsheetId=SHEET_ID,
            fields='sheets.properties.title',
        ).execute()
        disponibles = {s['properties']['title'] for s in meta.get('sheets', [])}

        totales = {}

        for tab in TABS_FALTANTES:
            if tab not in disponibles:
                logger.warning("Pestaña no encontrada en el sheet: %s", tab)
                continue

            # Fila 1: encabezado de zona; fila 2: encabezado de columnas; datos desde fila 3
            rng    = f"'{tab}'!A3:O1000"
            result = sheets.values().get(spreadsheetId=SHEET_ID, range=rng).execute()
            rows   = result.get('values', [])

            for row in rows:
                if len(row) < 3:
                    continue

                codigo_estacion = str(row[0]).strip()
                if not codigo_estacion:
                    continue

                clasificacion = row[14].strip().lower() if len(row) > 14 else ''
                if clasificacion not in CLASIFICACIONES_VALIDAS:
                    continue

                team_key = _estacion_to_team_key(codigo_estacion)
                if team_key is None:
                    logger.debug("Estación sin mapeo: %s", codigo_estacion)
                    continue

                monto = _parse_monto(row[2])
                totales[team_key] = totales.get(team_key, 0.0) + monto

        return totales, None

    except HttpError as e:
        logger.error("Sheets API HttpError (faltantes): %s", e)
        return {}, f"Error de Google Sheets API: {e.reason}"
    except Exception as e:
        logger.exception("Error leyendo faltantes del sheet")
        return {}, str(e)
