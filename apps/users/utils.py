from datetime import datetime

def parse_fecha(fecha_str):
    """
    Intenta convertir una cadena en fecha. Devuelve None si es inválida.
    Soporta múltiples formatos (ej. 28/11/2022, 2022-11-28, etc).
    """
    if not fecha_str or not fecha_str.strip():
        return None

    fecha_str = fecha_str.strip()
    formatos_posibles = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z"]

    for fmt in formatos_posibles:
        try:
            return datetime.strptime(fecha_str, fmt).date()
        except ValueError:
            continue

    return None
