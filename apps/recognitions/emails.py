# apps/recognitions/emails.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.urls import reverse
from django.conf import settings
from django.utils.html import strip_tags
from django.utils.text import Truncator
from html import unescape

def _unescape_recursive(s: str, rounds: int = 3) -> str:
    for _ in range(rounds):
        new = unescape(s or "")
        if new == s:
            break
        s = new
    return s

def _build_teaser(text: str, limit=240) -> str:
    raw = strip_tags(text or "")
    raw = _unescape_recursive(raw).replace("\xa0", " ")
    return Truncator(raw.strip()).chars(limit)

def _resolve_recipients(email_channels=None) -> list[str]:
    # Respeta override de QA
    test = (getattr(settings, "TEST_NEWS_EMAIL", "") or "").strip()
    if test:
        return [e.strip() for e in test.split(",") if e.strip()]
    channels = email_channels or ["corpo"]
    return settings.RESOLVE_NEWS_EMAILS(channels)

def send_recognition_email(recognition, *, email_channels=None) -> bool:
    to_addrs = _resolve_recipients(email_channels=email_channels)
    if not to_addrs:
        return False

    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")

    dashboard_url = reverse('recognition_dashboard_user')
    rec_url = f"{base}{dashboard_url}?highlight={recognition.id}#recognition-{recognition.id}"

    cat = getattr(recognition, "category", None)

    cover_url = ""
    try:
        media_rel = getattr(recognition, "media", None)
        first_media = media_rel.order_by("id").first() if media_rel is not None else None
        if first_media and getattr(first_media, "file", None) and getattr(first_media.file, "url", ""):
            cover_url = f"{base}{first_media.file.url}"
    except Exception:
        cover_url = ""

    if not cover_url and cat and getattr(cat, "cover_image", None) and getattr(cat.cover_image, "url", ""):
        cover_url = f"{base}{cat.cover_image.url}"

    if not cover_url:
        cover_url = f"{base}/static/template/img/logos/LOGOTIPO.png"

    # Paso A: Revisar si hay un asunto manual en el formulario
    raw_subject = getattr(recognition, 'email_subject', '')
    custom_subject = (raw_subject or "").strip()

    if custom_subject:
        # PRIORIDAD 1: Usar el asunto que escribió el usuario
        subject = custom_subject
        
    else:
        # PRIORIDAD 2: Generación Automática
        cat_title = cat.title if cat else 'Comunicado'
        subject = f"Nuevo Comunicado: {cat_title}"

        # Caso Especial: Cumpleaños
        if cat and "CUMPLEAÑOS" in cat_title.upper():
            target_name = "COLABORADOR"
            nombre_corto = ""
            apellido_corto = ""
            user_obj = None

            # Buscar usuario en tabla intermedia
            try:
                relacion = recognition.recognitionrecipient_set.select_related('user').first()
                if relacion and relacion.user:
                    user_obj = relacion.user
            except Exception:
                if hasattr(recognition, 'recipients'):
                    user_obj = recognition.recipients.first()

            # Extraer nombres limpios
            if user_obj:
                if user_obj.first_name:
                    nombre_corto = user_obj.first_name.strip().split()[0]
                if user_obj.last_name:
                    apellido_corto = user_obj.last_name.strip().split()[0]

            # Formatear nombre
            if nombre_corto or apellido_corto:
                target_name = f"{nombre_corto} {apellido_corto}".strip()
            
            subject = f"¡¡FELIZ CUMPLEAÑOS!! {target_name.upper()}"


    teaser = _build_teaser(recognition.message, limit=80)

    ctx = {
        "rec": recognition,
        "rec_url": rec_url,
        "cover_url": cover_url,
        "teaser": teaser,
    }

    try:
        html_body = render_to_string("recognitions/emails/recognition_created.html", ctx)
        text_body = render_to_string("recognitions/emails/recognition_created.txt", ctx)
    except (TemplateDoesNotExist, TemplateSyntaxError):
        text_body = f"Nuevo comunicado\n\n{teaser}\n\nVer: {rec_url}\n"
        html_body = (
            f"<img src='{cover_url}' alt='' width='600' "
            f"style='display:block;width:100%;max-width=600px;height:auto;border:0;'/>"
            f"<h2 style='font-family:Arial,sans-serif'>Nuevo comunicado</h2>"
            f"<p>{teaser}</p>"
            f"<p><a href='{rec_url}'>Ver comunicado</a></p>"
        )

    msg = EmailMultiAlternatives(
        subject,
        text_body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to_addrs,
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True
