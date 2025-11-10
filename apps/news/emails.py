# apps/news/emails.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

def get_news_recipients(news):
    test = getattr(settings, "TEST_NEWS_EMAIL", "").strip()
    return [test] if test else []

def send_news_email(news):
    to = get_news_recipients(news)
    if not to:
        return 0

    base = settings.SITE_BASE_URL.rstrip('/')
    news_url = f"{base}{reverse('news_detail_user', args=[news.id])}"

    # Portada si existe; si no, logo
    cover_url = ""
    try:
        if getattr(news, "cover_image") and getattr(news.cover_image, "url", ""):
            cover_url = f"{base}{news.cover_image.url}"  # /media/... -> http(s)://.../media/...
    except Exception:
        cover_url = ""

    if not cover_url:
        cover_url = f"{base}/static/template/img/logos/LOGOTIPO.png"

    subject = f"Nueva noticia: {news.title}"
    ctx = {"news": news, "news_url": news_url, "cover_url": cover_url}

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
        subject, text_body, getattr(settings, "DEFAULT_FROM_EMAIL", None), to
    )
    msg.attach_alternative(html_body, "text/html")
    sent = msg.send(fail_silently=False)

    type(news).objects.filter(pk=news.pk, emailed_at__isnull=True).update(emailed_at=timezone.now())
    return sent
