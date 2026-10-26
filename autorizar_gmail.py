"""
Script de autorización OAuth2 para Gmail — ejecutar UNA SOLA VEZ.

Uso:
  python autorizar_gmail.py

1. Se mostrará un URL — ábrelo en tu navegador e inicia sesión.
2. Google te redirigirá a http://localhost/... (la página no cargará, es normal).
3. Copia el URL COMPLETO de la barra del navegador y pégalo aquí.
"""

import os
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/directory.readonly',
]
CLIENT_FILE = os.path.join('credentials', 'gmail_oauth_client.json')
TOKEN_FILE  = os.path.join('credentials', 'gmail_token.json')

if not os.path.exists(CLIENT_FILE):
    print(f"ERROR: No se encontró {CLIENT_FILE}")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_FILE, SCOPES, redirect_uri='http://localhost'
)

auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

print("=" * 60)
print("Abre este URL en tu navegador:")
print()
print(auth_url)
print()
print("=" * 60)
print("Google te redirigirá a http://localhost/... (no cargará, es normal).")
print("Copia el URL COMPLETO de la barra del navegador y pégalo aquí:")
print()

redirect_response = input("URL completo: ").strip()

# Extraer el code del URL pegado
parsed = urlparse(redirect_response)
params = parse_qs(parsed.query)
code = params.get('code', [None])[0]

if not code:
    print("ERROR: No se encontró el código en el URL. Intenta de nuevo.")
    exit(1)

flow.fetch_token(code=code)
creds = flow.credentials

with open(TOKEN_FILE, 'w') as f:
    f.write(creds.to_json())

print()
print(f"¡Listo! Token guardado en: {TOKEN_FILE}")
