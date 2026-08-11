"""
Servicio para importar el presupuesto mensual de ventas desde Gmail.

Flujo:
  1. Autenticación OAuth2 con token almacenado en credentials/gmail_token.json
  2. Búsqueda del correo de presupuesto del mes indicado
  3. Extracción y parseo de la tabla HTML del cuerpo del correo
  4. Retorno de filas listas para guardar en PresupuestoVenta
"""

import os
import base64
import logging
import re
from datetime import date

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Scope de solo lectura — no puede modificar ni enviar correos
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CREDS_DIR  = os.path.join(_BASE_DIR, 'credentials')
_CLIENT_FILE = os.path.join(_CREDS_DIR, 'gmail_oauth_client.json')   # descargado de Google Cloud
_TOKEN_FILE  = os.path.join(_CREDS_DIR, 'gmail_token.json')           # se genera la primera vez

REMITENTE        = 'gerente.operaciones@totalgas.com'
ASUNTO_KEYWORDS  = ['presupuesto de ventas']

MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def _get_service():
    """Retorna el cliente autenticado de Gmail. Renueva el token si venció."""
    creds = None

    if os.path.exists(_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Primera vez: abre el navegador para autorizar
            flow = InstalledAppFlow.from_client_secrets_file(_CLIENT_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(_TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Búsqueda del correo
# ---------------------------------------------------------------------------

def _build_query(mes: date, remitente: str = None) -> str:
    """Construye el query de búsqueda de Gmail para el mes dado."""
    nombre_mes = [k for k, v in MESES_ES.items() if v == mes.month][0]
    from_addr = remitente or REMITENTE
    return (
        f'from:{from_addr} '
        f'subject:"presupuesto de ventas" '
        f'subject:"{nombre_mes}"'
    )


def _get_body_html(service, msg_id: str) -> str:
    """Extrae el HTML del cuerpo del mensaje."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    def _extract(parts):
        for part in parts:
            mime = part.get('mimeType', '')
            body_data = part.get('body', {}).get('data', '')
            if mime == 'text/html' and body_data:
                return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            if 'parts' in part:
                result = _extract(part['parts'])
                if result:
                    return result
        return ''

    payload = msg.get('payload', {})
    # Mensaje simple (sin multipart)
    if payload.get('mimeType') == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')

    return _extract(payload.get('parts', []))


# ---------------------------------------------------------------------------
# Parseo de la tabla HTML
# ---------------------------------------------------------------------------

def _limpiar_numero(texto: str) -> float:
    """Convierte '1,215,004' o '' o None a float."""
    if not texto:
        return 0.0
    limpio = re.sub(r'[,$\s\xa0]', '', texto.strip())
    try:
        return float(limpio) if limpio else 0.0
    except ValueError:
        return 0.0


def _parsear_tabla(html: str) -> list[dict]:
    """
    Extrae las filas de datos del presupuesto de la tabla HTML del correo.

    Retorna lista de dicts:
      {codigo, maxima, gasolina_super, diesel, total}
    """
    soup = BeautifulSoup(html, 'lxml')
    filas_resultado = []

    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        datos = []
        for row in rows:
            celdas = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if celdas:
                datos.append(celdas)

        # Buscar la tabla que tenga filas con código numérico en col 0
        filas_validas = []
        for celdas in datos:
            if len(celdas) < 3:
                continue
            cod = re.sub(r'\D', '', celdas[0])  # quitar no-dígitos
            if cod and len(cod) >= 3:
                filas_validas.append((cod, celdas))

        if not filas_validas:
            continue

        # Esta es la tabla correcta
        for cod, celdas in filas_validas:
            # Columnas esperadas: código | nombre | maxima | super | diesel | total
            maxima = _limpiar_numero(celdas[2] if len(celdas) > 2 else '')
            super_ = _limpiar_numero(celdas[3] if len(celdas) > 3 else '')
            diesel = _limpiar_numero(celdas[4] if len(celdas) > 4 else '')
            total  = _limpiar_numero(celdas[5] if len(celdas) > 5 else '')

            filas_resultado.append({
                'codigo':         cod,
                'maxima':         maxima,
                'gasolina_super': super_,
                'diesel':         diesel,
                'total':          total,
            })

        break  # ya encontramos la tabla correcta

    return filas_resultado


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def importar_presupuesto(mes: date, remitente: str = None) -> dict:
    """
    Busca en Gmail el correo de presupuesto para el mes dado y retorna los datos.

    Args:
        mes: primer día del mes a importar (ej. date(2026, 8, 1))

    Returns:
        {
          'filas': [...],       # datos listos para guardar
          'msg_id': str,        # ID del mensaje de Gmail procesado
          'error': str | None,  # mensaje de error si falló
        }
    """
    try:
        service = _get_service()
    except Exception as exc:
        return {'filas': [], 'msg_id': None, 'error': f'Error de autenticación: {exc}'}

    query = _build_query(mes, remitente=remitente)
    logger.info("Gmail query: %s", query)

    try:
        resultado = service.users().messages().list(
            userId='me', q=query, maxResults=5
        ).execute()
    except Exception as exc:
        return {'filas': [], 'msg_id': None, 'error': f'Error al buscar correos: {exc}'}

    mensajes = resultado.get('messages', [])
    if not mensajes:
        nombre_mes = [k for k, v in MESES_ES.items() if v == mes.month][0]
        return {
            'filas': [],
            'msg_id': None,
            'error': f'No se encontró correo de presupuesto para {nombre_mes} {mes.year}',
        }

    # Tomar el más reciente (el primero que retorna Gmail)
    msg_id = mensajes[0]['id']

    try:
        html = _get_body_html(service, msg_id)
    except Exception as exc:
        return {'filas': [], 'msg_id': msg_id, 'error': f'Error al leer el correo: {exc}'}

    if not html:
        return {'filas': [], 'msg_id': msg_id, 'error': 'El correo no tiene contenido HTML'}

    filas = _parsear_tabla(html)
    if not filas:
        return {'filas': [], 'msg_id': msg_id, 'error': 'No se encontró tabla de presupuesto en el correo'}

    return {'filas': filas, 'msg_id': msg_id, 'error': None}
