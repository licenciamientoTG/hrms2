from django.shortcuts import render, redirect, get_object_or_404
from .models import News, NewsTag, NewsLike, NewsComment
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime
from django.utils.timezone import make_aware, get_current_timezone
from django.db.models import Q, Count, Exists, OuterRef, Prefetch
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest, Http404
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils.timesince import timesince
from django.db.models import Value, CharField, F
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_GET
from .services import publish_news_if_due
from django.core.mail import send_mail
from django.conf import settings


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
    q = (request.GET.get('q') or '').strip()

    my_like = Exists(
        NewsLike.objects.filter(news=OuterRef('pk'), user=request.user)
    )

    qs = (News.objects
          .select_related('author')
          .prefetch_related('tags')
          .filter(published_at__isnull=False))  # <-- ya publicada

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(content__icontains=q) |
            Q(tags__name__icontains=q)
        ).distinct()

    news = (qs
            .annotate(
                like_count=Count('like_set', distinct=True),
                my_liked=my_like,
                comment_count=Count('comments', distinct=True),
            )
            .order_by('-published_at'))  # <-- orden por fecha real de publicación

    return render(request, 'news/user/news_view_user.html', {'news': news, 'q': q})

# esta vista es para que el administrador pueda editar las noticias
@user_passes_test(lambda u: u.is_superuser, login_url='user_news')
def news_detail_admin(request, pk):
    news = get_object_or_404(News, pk=pk)
    tags = NewsTag.objects.all().order_by('name')

    if request.method == 'POST':
        # Texto / booleans
        news.title        = (request.POST.get('title') or '').strip()
        news.content      = request.POST.get('content') or ''  # HTML desde TinyMCE
        news.audience     = request.POST.get('audience', 'all')
        news.notify_email = bool(request.POST.get('notify_email'))
        news.notify_push  = bool(request.POST.get('notify_push'))

        # Programar publicación (input type="datetime-local" => YYYY-MM-DDTHH:MM)
        raw_dt = request.POST.get('publish_at')
        if raw_dt:
            try:
                naive = datetime.strptime(raw_dt, "%Y-%m-%dT%H:%M")
                news.publish_at = make_aware(naive, get_current_timezone())
            except Exception:
                # si falla el parseo, mejor limpiarlo que dejar un valor inválido
                news.publish_at = None
        else:
            news.publish_at = None

        # Portada
        if request.POST.get('clear_cover') == 'on':
            if news.cover_image:
                news.cover_image.delete(save=False)
            news.cover_image = None
        elif 'cover_image' in request.FILES:
            news.cover_image = request.FILES['cover_image']

        # Adjunto (si tu modelo tiene un FileField llamado attachments)
        if request.POST.get('clear_attachment') == 'on':
            if news.attachments:
                news.attachments.delete(save=False)
            news.attachments = None
        elif 'attachments' in request.FILES:
            news.attachments = request.FILES['attachments']

        news.save()

        # Tags (ManyToMany)
        tag_ids = request.POST.getlist('tags')  # lista de strings
        news.tags.set(tag_ids)

        # PUBLICAR + ENVIAR si ya toca
        publish_news_if_due(news)

        return redirect('news_detail_admin', pk=news.pk)


    # GET (o tras redirect): siempre calcula comments y renderiza
    comments = (
        NewsComment.objects
        .filter(news=news)
        .select_related('user')
        .order_by('-created_at')
    )

    # Normaliza el texto para el template
    for c in comments:
        c.display_text = (c.body or '').strip()

    return render(request, 'news/admin/news_details_admin.html', {
        'news': news,
        'tags': tags,
        'comments': comments,
    })

# esta vista es para que el usuario vea los detalles de la noticia
@login_required
def news_detail_user(request, pk):
    my_like = Exists(
        NewsLike.objects.filter(news=OuterRef('pk'), user=request.user)
    )

    comments_qs = NewsComment.objects.select_related('user').order_by('-created_at')

    qs = (News.objects
          .select_related('author')
          .prefetch_related(Prefetch('comments', queryset=comments_qs))
          .annotate(
              like_count=Count('like_set', distinct=True),
              comment_count=Count('comments', distinct=True),
              my_liked=my_like,
          ))

    n = get_object_or_404(qs, pk=pk)

    # Si no está publicada, no la muestres al usuario final
    if not request.user.is_superuser and not n.published_at:
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
        content      = request.POST.get('content', '')
        cover_image  = request.FILES.get('cover_image')
        attachment   = request.FILES.get('attachments')
        audience     = request.POST.get('audience', 'all')
        notify_email = bool(request.POST.get('notify_email'))
        notify_push  = bool(request.POST.get('notify_push'))
        tag_ids      = request.POST.getlist('tags')

        # ✅ ahora múltiple
        email_channels = request.POST.getlist('email_channels') if notify_email else []

        # Parsear datetime-local → aware
        publish_at = None
        raw = request.POST.get('publish_at')
        if raw:
            try:
                naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
                publish_at = make_aware(naive, get_current_timezone())
            except Exception:
                publish_at = None

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

        # ⬇️ respeta canales elegidos
        publish_news_if_due(news, email_channels=email_channels)

        return redirect('admin_news')

    tags = NewsTag.objects.all().order_by('name')
    return render(request, 'news/admin/create_news.html', {'available_tags': tags})

# esta vista es para que el usuario pueda dar like a una noticia
@login_required
def news_like_toggle(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')

    n = get_object_or_404(News, pk=pk)

    obj, created = NewsLike.objects.get_or_create(news=n, user=request.user)
    if created:
        liked = True
    else:
        obj.delete()
        liked = False

    # Conteo actualizado
    count = NewsLike.objects.filter(news=n).count()

    return JsonResponse({'ok': True, 'liked': liked, 'count': count})

# esta vista es para crear comentarios
@login_required
@require_POST
def news_comment_create(request, pk):
    news = get_object_or_404(News, pk=pk)
    body = (request.POST.get('body') or '').strip()
    if not body:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)

    c = NewsComment.objects.create(news=news, user=request.user, body=body)

    # Render del comentario como HTML (partial)
    html = render_to_string('news/user/_comment.html', {'c': c, 'request': request}, request=request)

    return JsonResponse({
        'ok': True,
        'html': html,
        'count': news.comments.count(),
        'id': c.id,
    })

@require_POST
@login_required
def news_comment_delete(request, pk, cid):
    news = get_object_or_404(News, pk=pk)
    comment = get_object_or_404(NewsComment, pk=cid, news=news)

    user = request.user
    is_owner = (getattr(comment, 'user_id', None) == user.id)  # o comment.author_id si tu campo se llama así
    can_moderate = user.has_perm('news.delete_newscomment')    # 👈 sin exigir is_staff
    is_super = user.is_superuser

    if not (is_owner or can_moderate or is_super):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        return HttpResponseForbidden('No autorizado')

    comment.delete()
    new_count = NewsComment.objects.filter(news=news).count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'id': cid, 'count': new_count})

    next_url = request.META.get('HTTP_REFERER') or reverse('news_detail', args=[pk])
    return redirect(next_url)

# esta vista es la visualizacion de los likes
# === helpers ===
def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""

def _display_name(user) -> str:
    fn = _first_token(getattr(user, 'first_name', ''))
    ln = _first_token(getattr(user, 'last_name', ''))
    full = f"{fn} {ln}".strip()
    return full or user.get_username()

# === vista likes: soporta M2M directa o modelo intermedio ===
@require_GET
@login_required
def news_likes_list(request, pk):
    news = get_object_or_404(News, pk=pk)

    # Opción A: ManyToMany directa "news.likes" (usuarios)
    likes_m2m = getattr(news, 'likes', None)
    if likes_m2m is not None:
        users_qs = likes_m2m.all().order_by('id')
        items = [{"name": _display_name(u), "liked_at": ""} for u in users_qs]
        return JsonResponse({
            "news_id": news.id,
            "title": news.title,
            "count": users_qs.count(),
            "items": items,
        })

    # Opción B: modelo intermedio NewsLike(user, news, created_at)
    qs = (NewsLike.objects
          .filter(news=news)
          .select_related('user')
          .order_by('-created_at'))

    items = [{
        "name": _display_name(like.user),
        "liked_at": timesince(getattr(like, 'created_at', now()), now()) + " atrás",
    } for like in qs]

    return JsonResponse({
        "news_id": news.id,
        "title": news.title,
        "count": qs.count(),
        "items": items,
    })