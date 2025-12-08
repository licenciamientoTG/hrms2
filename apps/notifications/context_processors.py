# apps/notifications/context_processors.py
from django.db.models import Count
from .models import Notification

def notifications_context(request):
    if not request.user.is_authenticated:
        return {}

    # Quitamos el ordering por defecto del modelo con .order_by()
    qs = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True
    ).order_by()  # 👈 esto limpia el ORDER BY (-created_at)

    per_module = {
        (row['module'] or ''): row['total']
        for row in qs
              .values('module')
              .annotate(total=Count('id'))
              .order_by('module')   # 👈 opcional, pero aquí sí es válido
    }

    return {
        'notif_total_unread': sum(per_module.values()),
        'notif_module_counts': per_module,
    }
