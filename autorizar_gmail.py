"""
Script de autorización OAuth2 para Gmail — ejecutar UNA SOLA VEZ.

Si usas VS Code Remote SSH, el puerto 8888 se reenvía automáticamente
a tu computadora. Solo abre el link que aparece en la terminal.

Uso:
  python autorizar_gmail.py
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES      = ['https://www.googleapis.com/auth/gmail.readonly']
CLIENT_FILE = os.path.join('credentials', 'gmail_oauth_client.json')
TOKEN_FILE  = os.path.join('credentials', 'gmail_token.json')

if not os.path.exists(CLIENT_FILE):
    print(f"ERROR: No se encontró {CLIENT_FILE}")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)

print("Iniciando servidor local en puerto 8888...")
print("Se abrirá el navegador — inicia sesión con bernardo.cardenas@totalgas.com")
print("Si no abre solo, ve a: http://localhost:8888")
print()

creds = flow.run_local_server(port=8888, open_browser=False)

with open(TOKEN_FILE, 'w') as f:
    f.write(creds.to_json())

print()
print(f"¡Listo! Token guardado en: {TOKEN_FILE}")
print("El sistema ya puede importar presupuestos automáticamente.")
