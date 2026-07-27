# Team keys de estaciones del Bajío (reciben $240 de bono de venta, sin importar antigüedad)
BAJIO_TEAM_KEYS = {
    '11007',           # Independencia/Aguascalientes
    '1376',            # Delicias
    '12900',           # El Castaño
    'Picachos',
    'Ventanas',
    'San Rafael',
    'Puertecito',
    'Jesus Maria',
    'Gabriela Mistral',
    'Colosio',
}

STATION_TEAMS = {
    '4188': 'Gemela Grande',
    '11007': 'Aguascalientes/Independencia',
    '1149': 'Lerdo',
    '2526': 'Lopez Mateos',
    '4179': 'Gemela Chica',
    '5317': 'Municipio Libre',
    '5465': 'Aztecas',
    '6410': 'Misiones',
    '6947': 'Puerto de Palos',
    '7167': 'Miguel de la Madrid',
    '8244': 'Permuta',
    '9191': 'Electrolux',
    '9235': 'Aeronáutica',
    '9885': 'Custodia',
    '9893': 'Anapra',
    '2172': 'Parral',
    '1376': 'Delicias',
    '5170': 'Plutarco',
    '1163': 'Tecnológico',
    '23214': 'Hermanos Escobar',
    '12900': 'El Castaño',
    'Ejercito': 'Ejército Nacional',
    'Satelite': 'Satélite',
    'Fuentes': 'Las Fuentes',
    'Clara': 'Clara',
    'Solis': 'Solis',
    'Santiago': 'Santiago Troncoso',
    'Jarudo': 'Jarudo',
    'Villahumada': 'Villa Ahumada',
    'Travel Center': 'Travel Center',
    'Picachos': 'Picachos',
    'Ventanas': 'Ventanas',
    'San Rafael': 'San Rafael',
    'Puertecito': 'Puertecito',
    'Jesus Maria': 'Jesús María',
    'Gabriela Mistral': 'Gabriela Mistral',
    'Praxedis': 'PRAXEDIS',
    'Colosio': 'Colosio',
}

# Mapeo de códigos numéricos del Excel → key en STATION_TEAMS
# Para las estaciones cuyo Employee.team usa clave de texto, no número.
EXCEL_CODE_TO_TEAM_KEY = {
    '9733':  'Ejercito',
    '9773':  'Ejercito',
    '4457':  'Satelite',
    '1159':  'Fuentes',
    '1156':  'Clara',
    '10141': 'Solis',
    '12097': 'Santiago',
    '1148':  'Jarudo',
    '1242':  'Villahumada',
    '24938': 'Travel Center',
    '24499': 'Picachos',
    '24500': 'Ventanas',
    '14946': 'San Rafael',
    '15071': 'Puertecito',
    '15091': 'Jesus Maria',
    '15901': 'Jesus Maria',
    '12442': 'Gabriela Mistral',
    '3184':  'Praxedis',
    '10702': 'Praxedis',
    '22600': 'Colosio',
}

# Mapeo de códigos de ControlGas (SG12.EstacionCod) → key en STATION_TEAMS
# Difiere de EXCEL_CODE_TO_TEAM_KEY en: Ejercito (9773 vs 9733) y Praxedis (10702 vs 3184)
CG_CODE_TO_TEAM_KEY = {
    '9773':  'Ejercito',
    '4457':  'Satelite',
    '1159':  'Fuentes',
    '1156':  'Clara',
    '10141': 'Solis',
    '12097': 'Santiago',
    '1148':  'Jarudo',
    '1242':  'Villahumada',
    '24938': 'Travel Center',
    '24499': 'Picachos',
    '24500': 'Ventanas',
    '14946': 'San Rafael',
    '15071': 'Puertecito',
    '15091': 'Jesus Maria',
    '15901': 'Jesus Maria',
    '12442': 'Gabriela Mistral',
    '10702': 'Praxedis',
    '22600': 'Colosio',
}

# Reverso: team_key → código numérico de display (N.o en el Excel/ControlGas)
TEAM_KEY_TO_CG_CODE = {v: k for k, v in CG_CODE_TO_TEAM_KEY.items()}

# Orden exacto del Excel y N.o que se muestra en la primera columna del dashboard
# (excel_no, team_key)
EXCEL_STATION_ORDER = [
    ('1148',  'Jarudo'),
    ('1149',  '1149'),
    ('1156',  'Clara'),
    ('1159',  'Fuentes'),
    ('1163',  '1163'),
    ('1242',  'Villahumada'),
    ('1376',  '1376'),
    ('2172',  '2172'),
    ('2526',  '2526'),
    ('4179',  '4179'),
    ('4188',  '4188'),
    ('4457',  'Satelite'),
    ('5170',  '5170'),
    ('5317',  '5317'),
    ('5465',  '5465'),
    ('6410',  '6410'),
    ('6947',  '6947'),
    ('7167',  '7167'),
    ('8244',  '8244'),
    ('9191',  '9191'),
    ('9235',  '9235'),
    ('9773',  'Ejercito'),
    ('9885',  '9885'),
    ('10141', 'Solis'),
    ('9893',  '9893'),
    ('11007', '11007'),
    ('12097', 'Santiago'),
    ('12900', '12900'),
    ('23214', '23214'),
    ('24499', 'Picachos'),
    ('24500', 'Ventanas'),
    ('24938', 'Travel Center'),
    ('3184',  'Praxedis'),
    ('22600', 'Colosio'),
    ('15091', 'Jesus Maria'),
    ('15071', 'Puertecito'),
    ('14946', 'San Rafael'),
    ('12442', 'Gabriela Mistral'),
]

# Lookup rápido: team_key → (posición, excel_no)
EXCEL_ORDER_LOOKUP = {tk: (pos, no) for pos, (no, tk) in enumerate(EXCEL_STATION_ORDER)}

# Mapeo de EstacionCod (entero interno de SG12) → team_key en STATION_TEAMS
SG12_COD_TO_TEAM_KEY = {
    2:  '4188',          # Gemela Grande
    3:  '11007',         # Independencia
    5:  '1149',          # Lerdo
    6:  '2526',          # Lopez Mateos
    7:  '4179',          # Gemela Chica
    8:  '5317',          # Municipio Libre
    9:  '5465',          # Aztecas
    10: '6410',          # Misiones
    11: '6947',          # Puerto de Palos
    12: '7167',          # Miguel de la Madrid
    13: '8244',          # Permuta
    14: '9191',          # Electrolux
    15: '9235',          # Aeronáutica
    16: '9885',          # Custodia
    17: '9893',          # Anapra
    18: '2172',          # Parral
    19: '1376',          # Delicias
    20: '5170',          # Plutarco (Servicio Agil)
    21: '5170',          # Plutarco (Estacion Custodia)
    22: '1163',          # Tecnológico
    23: 'Ejercito',      # Ejército Nacional
    24: 'Satelite',      # Satélite
    25: 'Fuentes',       # Las Fuentes
    26: 'Clara',         # Clara
    27: 'Solis',         # Solis
    28: 'Santiago',      # Santiago Troncoso
    29: 'Jarudo',        # Jarudo
    30: '23214',         # Hermanos Escobar
    31: 'Villahumada',   # Villa Ahumada
    32: '12900',         # El Castaño
    33: 'Travel Center', # Travel Center
    34: 'Picachos',      # Picachos
    35: 'Ventanas',      # Ventanas
    36: 'San Rafael',    # San Rafael
    37: 'Puertecito',    # Puertecito
    38: 'Jesus Maria',   # Jesús María
    39: 'Gabriela Mistral', # Gabriela Mistral
    40: 'Praxedis',     # PRAXEDIS
}
