import ipaddress
import requests

PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]

def get_client_ip(request):
    """Devuelve la IP pública real si viene en X-Forwarded-For; si no, REMOTE_ADDR."""
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # primera IP no privada
        for raw in [p.strip() for p in xff.split(",")]:
            try:
                ip = ipaddress.ip_address(raw)
                if not any(ip in n for n in PRIVATE_NETS):
                    return raw
            except ValueError:
                continue
    return request.META.get("REMOTE_ADDR")

def is_private_ip(ip: str) -> bool:
    try:
        ipobj = ipaddress.ip_address(ip)
        return any(ipobj in n for n in PRIVATE_NETS)
    except Exception:
        return True

def geo_city_light(ip: str):
    """
    Devuelve (country, region, city). Para IPs privadas devuelve vacíos.
    Usa ipapi.co (gratuita) con timeout corto y maneja errores silenciosamente.
    """
    if not ip or is_private_ip(ip):
        return ("", "", "")
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2)
        if r.status_code == 200:
            j = r.json()
            country = j.get("country_name", "") or ""
            region  = j.get("region", "") or ""
            city    = j.get("city", "") or ""
            return (country[:64], region[:64], city[:64])
    except Exception:
        pass
    return ("", "", "")
