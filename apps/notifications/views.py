from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.utils.timezone import now
from .models import Notification

@login_required
@require_GET
def api_list(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    unread = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    items = [{
        'id': n.id, 'title': n.title, 'body': n.body, 'url': n.url,
        'created_at': n.created_at.isoformat(), 'is_read': n.is_read
    } for n in qs]
    return JsonResponse({'ok': True, 'count': unread, 'items': items})

@login_required
@require_POST
def api_mark_all_read(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=now())
    return JsonResponse({'ok': True})
