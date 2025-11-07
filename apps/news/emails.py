from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

def get_news_recipients(news):
    # Durante QA: un destinatario fijo desde settings
    test = getattr(settings, "TEST_NEWS_EMAIL", "").strip()
    return [test] if test else []

def send_news_email(news):
    to = get_news_recipients(news)
    if not to:
        return 0

    subject = f"Nueva noticia: {news.title}"
    ctx = {"news": news}

    # Si no tienes plantillas, usamos fallback simple:
    try:
        html_body = render_to_string("news/emails/news_published.html", ctx)
        text_body = render_to_string("news/emails/news_published.txt", ctx)
    except Exception:
        text_body = f"{news.title}\n\n{news.content}"
        html_body = f"<h1>{news.title}</h1>{news.content}"

    msg = EmailMultiAlternatives(subject, text_body, getattr(settings, "DEFAULT_FROM_EMAIL", None), to)
    msg.attach_alternative(html_body, "text/html")
    sent = msg.send(fail_silently=False)

    # marca de envío para evitar duplicados
    type(news).objects.filter(pk=news.pk, emailed_at__isnull=True).update(emailed_at=timezone.now())
    return sent
