"""
Servicio para leer faltantes de gerentes/subgerentes desde Google Sheets.

Hoja DIARIOS: "Faltantes" (ID: 1HwJWddOpVvegUpolrxpX12M07fsyvhNp5slhO1muCgk)
  Pestañas: FALTANTES Z1 … Z4
  Uso: vista en tiempo real; entradas se eliminan al pagar.

Hoja F8:  "F8 FALTANTES (Respuestas)" (ID: 1tCKyJw-CUCuAR-pNBfYK0rJv600MXzVnyslrEHscFj0)
  Pestañas por año: '2026', '2027', …
  Columnas: A=ESTACION  C=IMPORTE  G=FECHA  O=REAL (SI/NO)
  Uso: histórico completo del año — fuente correcta para ECV semanal.
"""

import os
import logging
import re
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.incentives.constants import STATION_TEAMS, EXCEL_CODE_TO_TEAM_KEY

logger = logging.getLogger(__name__)

SHEET_ID    = '1HwJWddOpVvegUpolrxpX12M07fsyvhNp5slhO1muCgk'
F8_SHEET_ID = '1tCKyJw-CUCuAR-pNBfYK0rJv600MXzVnyslrEHscFj0'
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


# Estatus que indican faltante activo/pendiente de cobro.
# "DESCONTANDOSE VIA NOMINA" se excluye a propósito: una vez que el faltante
# ya se está cobrando vía nómina, el reporte oficial F8 SEMANAL deja de
# contarlo como pendiente — solo cuenta lo que sigue genuinamente abierto.
ESTATUS_ACTIVOS_F8 = {'ABIERTO'}


def _leer_filas_f8_abiertas():
    """
    Lee del F8 las filas crudas de faltantes actualmente abiertos, ya
    filtradas (REAL=SI, ESTATUS ∈ ESTATUS_ACTIVOS_F8) y con el team_key
    resuelto. Compartida por leer_faltantes_f8_abiertos() (totales por
    estación) y leer_faltantes_f8_abiertos_detalle() (fila por fila).

    No filtra por fecha — devuelve el estado actual de faltantes sin pagar,
    equivalente a lo que mostraría FALTANTES DIARIOS en el momento del cálculo.
    La pestaña se determina por el año actual.

    Returns
    -------
    (filas, error_str)
      filas: lista de (team_key, row, importe, estatus) — row es la fila
             cruda del sheet (para leer gerente/responsable/motivo/etc.)
      error_str: None si OK, mensaje si ocurrió error
    """
    tab = str(date.today().year)

    try:
        service = _get_service()
        sheets  = service.spreadsheets()

        meta = sheets.get(
            spreadsheetId=F8_SHEET_ID,
            fields='sheets.properties.title',
        ).execute()
        disponibles = {s['properties']['title'] for s in meta.get('sheets', [])}
        if tab not in disponibles:
            return [], f"Pestaña '{tab}' no encontrada en F8 FALTANTES"

        rng    = f"'{tab}'!A2:O20000"
        result = sheets.values().get(
            spreadsheetId=F8_SHEET_ID,
            range=rng,
            valueRenderOption='UNFORMATTED_VALUE',
        ).execute()
        rows = result.get('values', [])

        filas = []
        for row in rows:
            if len(row) < 3:
                continue

            # Col O (índice 14): REAL
            real = str(row[14]).strip().upper() if len(row) > 14 else ''
            if real != 'SI':
                continue

            # Col M (índice 12): ESTATUS — solo activos/abiertos
            estatus = str(row[12]).strip() if len(row) > 12 else ''
            if estatus not in ESTATUS_ACTIVOS_F8:
                continue

            # Col A (índice 0): ESTACION
            cod_raw = row[0]
            if cod_raw is None or cod_raw == '':
                continue
            if isinstance(cod_raw, (int, float)):
                cod = str(int(cod_raw))
            else:
                cod = str(cod_raw).strip()

            team_key = _estacion_to_team_key(cod)
            if team_key is None:
                logger.debug("F8: Estación sin mapeo: %s", cod)
                continue

            # Col C (índice 2): IMPORTE
            importe = _parse_monto(row[2]) if len(row) > 2 else 0.0
            if importe <= 0:
                continue

            filas.append((team_key, row, importe, estatus))

        return filas, None

    except HttpError as e:
        logger.error("Sheets API HttpError (F8 faltantes abiertos): %s", e)
        return [], f"Error de Google Sheets API: {e.reason}"
    except Exception as e:
        logger.exception("Error leyendo F8 faltantes abiertos")
        return [], str(e)


def leer_faltantes_f8_abiertos():
    """
    Lee del F8 todos los faltantes actualmente abiertos (sin contar los que
    ya están en descuento vía nómina — ver nota en ESTATUS_ACTIVOS_F8) y
    devuelve el total por estación.

    Returns
    -------
    (totales_dict, error_str)
      totales_dict : {team_key: float}
      error_str    : None si OK, mensaje si ocurrió error
    """
    filas, error = _leer_filas_f8_abiertas()
    if error:
        return {}, error
    totales = {}
    for team_key, _row, importe, _estatus in filas:
        totales[team_key] = totales.get(team_key, 0.0) + importe
    return totales, None


_EXCEL_EPOCH = date(1899, 12, 30)


def _serial_to_date(value):
    """Convierte un serial de fecha de Excel/Sheets (UNFORMATTED_VALUE) a date."""
    if isinstance(value, (int, float)):
        try:
            return _EXCEL_EPOCH + timedelta(days=int(value))
        except (OverflowError, ValueError):
            return None
    return None


def leer_faltantes_f8_abiertos_detalle():
    """
    Igual que leer_faltantes_f8_abiertos() pero devuelve el detalle fila
    por fila (gerente, responsable, motivo, fecha, etc.) en vez de solo el
    total por estación. Se usa para la hoja "Faltantes" del Excel ECV,
    réplica del detalle crudo que trae el Excel ECV Zona manual.

    Returns
    -------
    (filas, error_str)
      filas: lista de dicts con team_key, gerente, importe, responsable,
             motivo, turno, fecha (date|None), observaciones,
             dias_vigentes, razon_social, zona, estatus
      error_str: None si OK, mensaje si ocurrió error
    """
    filas_raw, error = _leer_filas_f8_abiertas()
    if error:
        return [], error
    return [
        {
            'team_key':      team_key,
            'gerente':       row[1]  if len(row) > 1  else '',
            'importe':       importe,
            'responsable':   row[3]  if len(row) > 3  else '',
            'motivo':        row[4]  if len(row) > 4  else '',
            'turno':         row[5]  if len(row) > 5  else '',
            'fecha':         _serial_to_date(row[6]) if len(row) > 6 else None,
            'observaciones': row[8]  if len(row) > 8  else '',
            'dias_vigentes': row[9]  if len(row) > 9  else None,
            'razon_social':  row[10] if len(row) > 10 else '',
            'zona':          row[11] if len(row) > 11 else '',
            'estatus':       estatus,
        }
        for team_key, row, importe, estatus in filas_raw
    ], None
