from django.shortcuts import render, redirect, get_object_or_404
from .models import News, NewsTag
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime
from django.utils.timezone import make_aware, get_current_timezone
from .models import News, NewsTag
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from .models import News

#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def news_view(request):
    if request.user.is_superuser:
        return redirect('admin_news')
    else:
        return redirect('user_news')

#esta vista nos dirige a la plantilla de nuestro administrador
@user_passes_test(lambda u: u.is_superuser, login_url='user_news')
def admin_news_view(request):
    q = request.GET.get('q', '').strip()
    news = (News.objects.select_related('author')
            .prefetch_related('tags')
            .order_by('-published_at'))
    if q:
        news = news.filter(
            Q(title__icontains=q) |
            Q(content__icontains=q) |
            Q(tags__name__icontains=q)
        ).distinct()
    return render(request, 'news/admin/news_view_admin.html', {'news': news, 'q': q})

#esta vista nos dirige a la plantilla de nuestro usuario
@login_required
def user_news_view(request):
    q = request.GET.get('q', '').strip()
    now = timezone.now()
    news = (News.objects.select_related('author')
            .prefetch_related('tags')
            .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
            .order_by('-published_at'))
    if q:
        news = news.filter(
            Q(title__icontains=q) |
            Q(content__icontains=q) |
            Q(tags__name__icontains=q)
        ).distinct()
    return render(request, 'news/user/news_view_user.html', {'news': news, 'q': q})

# esta vista es para que el administrador pueda editar las noticias
@user_passes_test(lambda u: u.is_superuser, login_url='user_news')
def news_detail_admin(request, pk):
    news = get_object_or_404(News, pk=pk)
    tags = NewsTag.objects.all().order_by('name')

    if request.method == 'POST':
        # Texto/booleans
        news.title        = request.POST.get('title', '').strip()
        news.content      = request.POST.get('content', '')            # ← HTML de TinyMCE
        news.audience     = request.POST.get('audience', 'all')
        news.notify_email = bool(request.POST.get('notify_email'))
        news.notify_push  = bool(request.POST.get('notify_push'))

        # Programación de publicación
        raw = request.POST.get('publish_at')
        if raw:
            try:
                naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
                news.publish_at = make_aware(naive, get_current_timezone())
            except Exception:
                pass
        else:
            news.publish_at = None

        # Portada (reemplazar / eliminar)
        if request.POST.get('clear_cover') == 'on':
            if news.cover_image:
                news.cover_image.delete(save=False)
            news.cover_image = None
        elif 'cover_image' in request.FILES:
            news.cover_image = request.FILES['cover_image']

        # Adjunto (reemplazar / eliminar)
        if request.POST.get('clear_attachment') == 'on':
            if news.attachments:
                news.attachments.delete(save=False)
            news.attachments = None
        elif 'attachments' in request.FILES:
            news.attachments = request.FILES['attachments']  # modelo actual: 1 archivo

        news.save()

        # Tags (ManyToMany)
        tag_ids = request.POST.getlist('tags')
        news.tags.set(tag_ids)

        return redirect('admin_news')  # o redirige a la misma página: redirect('news_detail_admin', pk=news.pk)

    return render(request, 'news/admin/news_details_admin.html', {
        'news': news,
        'available_tags': tags,
    })

# esta vista es para que el usuario vea los detalles de la noticia
@login_required
def news_detail_user(request, pk):
    n = (News.objects
            .select_related('author')
            .prefetch_related('tags')
            .get(pk=pk))
    # Si no es admin, no mostrar noticias programadas a futuro
    if not request.user.is_superuser and n.publish_at and n.publish_at > timezone.now():
        return redirect('user_news')
    return render(request, 'news/user/news_detail_user.html', {'n': n})

# esta vista es para que el administrador elimine noticias
@user_passes_test(lambda u: u.is_superuser, login_url='user_news')
def news_delete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    n = get_object_or_404(News, pk=pk)

    # Borra archivos físicos si existen
    try:
        if n.cover_image:
            n.cover_image.delete(save=False)
        if n.attachments:
            n.attachments.delete(save=False)
    except Exception:
        # si falla el borrado físico no bloqueamos la eliminación del registro
        pass

    title = n.title
    n.delete()

    return redirect('admin_news')

#esta es la vista para la plantilla de crear noticias
@user_passes_test(lambda u: u.is_superuser)
def create_news(request):
    if request.method == 'POST':
        title        = request.POST.get('title', '').strip()
        content      = request.POST.get('content', '')          # ← HTML del editor
        cover_image  = request.FILES.get('cover_image')         # imagen de portada
        attachment   = request.FILES.get('attachments')         # UN archivo (FileField)
        audience     = request.POST.get('audience', 'all')
        notify_email = bool(request.POST.get('notify_email'))
        notify_push  = bool(request.POST.get('notify_push'))
        tag_ids      = request.POST.getlist('tags')             # múltiples

        # Parsear datetime-local → aware
        publish_at = None
        raw = request.POST.get('publish_at')
        if raw:
            try:
                naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
                publish_at = make_aware(naive, get_current_timezone())
            except Exception:
                publish_at = None  # o maneja el error como prefieras

        news = News.objects.create(
            title=title,
            content=content,
            cover_image=cover_image,
            attachments=attachment,
            publish_at=publish_at,
            notify_email=notify_email,
            notify_push=notify_push,
            audience=audience,
            author=request.user
        )

        if tag_ids:
            news.tags.set(tag_ids)

        return redirect('admin_news')

    tags = NewsTag.objects.all().order_by('name')
    return render(request, 'news/admin/create_news.html', {'available_tags': tags})