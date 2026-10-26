"""
Servicio para consultar el directorio de Google Workspace via People API.
Usa el mismo token OAuth2 que Gmail (gmail_token.json).
"""

import os
import logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/directory.readonly',
]

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CREDS_DIR   = os.path.join(_BASE_DIR, 'credentials')
_TOKEN_FILE  = os.path.join(_CREDS_DIR, 'gmail_token.json')


def _get_people_service():
    """Retorna el cliente autenticado de People API."""
    if not os.path.exists(_TOKEN_FILE):
        raise FileNotFoundError(f"No se encontró el token: {_TOKEN_FILE}")

    creds = Credentials.from_authorized_user_file(_TOKEN_FILE, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(_TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('people', 'v1', credentials=creds, cache_discovery=False)


def get_directory_emails():
    """
    Obtiene todos los contactos del directorio de Google Workspace.
    Retorna lista de dicts: [{'name': '...', 'email': '...'}]
    """
    service = _get_people_service()
    results = []
    page_token = None

    while True:
        kwargs = dict(
            readMask='names,emailAddresses',
            pageSize=1000,
            sources=['DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE'],
        )
        if page_token:
            kwargs['pageToken'] = page_token

        resp = service.people().listDirectoryPeople(**kwargs).execute()

        for person in resp.get('people', []):
            names = person.get('names', [])
            emails = person.get('emailAddresses', [])
            if not names or not emails:
                continue
            name = names[0].get('displayName', '')
            email = emails[0].get('value', '')
            if name and email:
                results.append({'name': name, 'email': email})

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    return results
