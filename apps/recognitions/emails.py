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

    # URL destino
    try:
        rec_url = f"{base}{reverse('recognition_detail', args=[recognition.id])}"
    except Exception:
        rec_url = f"{base}{reverse('recognition_dashboard_user')}"

    # Categoría (se usa en asunto y posible fallback de portada)
    cat = getattr(recognition, "category", None)

    # Portada: 1) primera imagen subida  2) cover de categoría  3) logo
    cover_url = ""
    try:
        media_rel = getattr(recognition, "media", None)  # related_name de RecognitionMedia
        first_media = media_rel.order_by("id").first() if media_rel is not None else None
        if first_media and getattr(first_media, "file", None) and getattr(first_media.file, "url", ""):
            cover_url = f"{base}{first_media.file.url}"
    except Exception:
        cover_url = ""

    if not cover_url and cat and getattr(cat, "cover_image", None) and getattr(cat.cover_image, "url", ""):
        cover_url = f"{base}{cat.cover_image.url}"

    if not cover_url:
        cover_url = f"{base}/static/template/img/logos/LOGOTIPO.png"

    subject = f"Nuevo Comunicado: {cat.title if cat else 'Comunicado'}"
    teaser  = _build_teaser(recognition.message, limit=240)

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
        text_body = f"Nuevo reconocimiento\n\n{teaser}\n\nVer: {rec_url}\n"
        html_body = (
            f"<img src='{cover_url}' alt='' width='600' "
            f"style='display:block;width:100%;max-width=600px;height:auto;border:0;'/>"
            f"<h2 style='font-family:Arial,sans-serif'>Nuevo reconocimiento</h2>"
            f"<p>{teaser}</p>"
            f"<p><a href='{rec_url}'>Ver reconocimiento</a></p>"
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
