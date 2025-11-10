# apps/news/emails.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from html import unescape

def _unescape_recursive(s: str, rounds: int = 3) -> str:
    """Aplica html.unescape varias veces por si vienen entidades doble/tri-escapadas."""
    for _ in range(rounds):
        new = unescape(s or "")
        if new == s:
            break
        s = new
    return s

def _build_teaser(html, limit=240):
    raw = strip_tags(html or "")
    raw = _unescape_recursive(raw).replace("\xa0", " ")  # &nbsp; → espacio normal
    return Truncator(raw.strip()).chars(limit)

def get_news_recipients(news, email_channels=None) -> list[str]:
    test = (getattr(settings, "TEST_NEWS_EMAIL", "") or "").strip()
    if test:
        return [e.strip() for e in test.split(",") if e.strip()]

    channels = email_channels or ["corpo"]
    # Este helper lo definimos en settings.py
    return settings.RESOLVE_NEWS_EMAILS(channels)

def send_news_email(news, *, email_channels=None) -> bool:
    to_addrs = get_news_recipients(news, email_channels=email_channels)
    if not to_addrs:
        return False

    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    news_url = f"{base}{reverse('news_detail_user', args=[news.id])}"

    # Portada si existe; si no, logo de fallback
    cover_url = ""
    try:
        if getattr(news, "cover_image") and getattr(news.cover_image, "url", ""):
            cover_url = f"{base}{news.cover_image.url}"
    except Exception:
        cover_url = ""
    if not cover_url:
        cover_url = f"{base}/static/template/img/logos/LOGOTIPO.png"

    subject = f"Nueva noticia: {news.title}"
    teaser = _build_teaser(news.content, limit=240)
    ctx = {"news": news, "news_url": news_url, "cover_url": cover_url, "teaser": teaser}
    try:
        html_body = render_to_string("news/emails/news_published.html", ctx)
        text_body = render_to_string("news/emails/news_published.txt", ctx)
    except (TemplateDoesNotExist, TemplateSyntaxError):
        text_body = f"Nueva noticia: {news.title}\nVer noticia: {news_url}\n"
        html_body = (
            f"<img src='{cover_url}' alt='' style='max-width:100%;height:auto;'/>"
            f"<h1 style='font-family:Arial,sans-serif'>{news.title}</h1>"
            f"<p><a href='{news_url}'>Ver noticia completa</a></p>"
        )

    msg = EmailMultiAlternatives(
        subject,
        text_body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to_addrs,
    )
    msg.attach_alternative(html_body, "text/html")
    # Si falla, lanzará excepción; la captura la hace services.py
    msg.send(fail_silently=False)

    # 👇 Ya no actualizamos emailed_at aquí
    return True
