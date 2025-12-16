from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.utils.timezone import now
from .models import Notification
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator

@login_required
@require_GET
def api_list(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))

    qs = Notification.objects.filter(user=request.user).order_by("-created_at", "-id")
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    unread = qs.filter(read_at__isnull=True).count()

    items = [{
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "url": n.url,
        "created_at": n.created_at.isoformat(),
        "is_read": n.read_at is not None,
    } for n in page_obj]

    return JsonResponse({
        "ok": True,
        "count": unread,
        "items": items,
        "page": page,
        "has_next": page_obj.has_next(),
    })


@login_required
@require_POST
def api_mark_all_read(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=now())
    return JsonResponse({'ok': True})

@login_required
@require_POST
def api_mark_read(request, pk: int):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if n.read_at is None:
        n.read_at = now()
        n.save(update_fields=['read_at'])
    return JsonResponse({'ok': True})

@login_required
@require_POST
def api_mark_module_read(request, module_name):
    """Marca como leídas todas las notificaciones de un módulo específico para el usuario actual."""
    updated_count = Notification.objects.filter(
        user=request.user, 
        module=module_name, 
        read_at__isnull=True
    ).update(read_at=now())
    
    return JsonResponse({'ok': True, 'updated': updated_count})