from datetime import timedelta
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from apps.monitoring.models import SessionEvent


def humanize_delta(delta):
    if delta.days > 0:
        return f"{delta.days}d"
    h = delta.seconds // 3600
    if h > 0:
        return f"{h}h"
    m = (delta.seconds % 3600) // 60
    return f"{m}m"


@user_passes_test(lambda u: u.is_superuser)
def monitoring_view(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # --- Subqueries para último evento por usuario (1 consulta) ---
    last_ts_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"))
        .order_by("-ts")
        .values("ts")[:1]
    )
    last_event_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"))
        .order_by("-ts")
        .values("event")[:1]
    )

    # Filtro de búsqueda opcional
    q = (request.GET.get("q") or "").strip()
    users_qs = (
        User.objects.only("id", "username", "first_name", "last_name", "last_login")
        .filter(is_active=True)
    )
    if q:
        users_qs = (
            users_qs.filter(username__icontains=q)
            | users_qs.filter(first_name__icontains=q)
            | users_qs.filter(last_name__icontains=q)
        )

    # Annotate + ORDER: abiertos primero, luego más recientes
    users_qs = (
        users_qs
        .annotate(
            last_ts=Subquery(last_ts_sq),
            last_event=Subquery(last_event_sq),
            is_open=Case(  # 1 si el último evento fue login
                When(last_event=SessionEvent.LOGIN, then=1),
                default=0,
                output_field=IntegerField(),
            ),
            # actividad más reciente (cae a last_login si no hay eventos)
            last_activity=Coalesce("last_ts", "last_login"),
        )
        .order_by("-is_open", "-last_activity", "id")
    )

    # --- Paginación ---
    page_size = int(request.GET.get("page_size", 50))
    page_number = request.GET.get("page", 1)
    paginator = Paginator(users_qs, page_size)
    page_obj = paginator.get_page(page_number)
    user_ids = list(page_obj.object_list.values_list("id", flat=True))

    # --- Logins últimos 7 días (1 consulta) ---
    login_rows = (
        SessionEvent.objects
        .filter(event=SessionEvent.LOGIN, ts__gte=week_ago, user_id__in=user_ids)
        .values_list("user_id", "ts")
    )
    usage_map = {uid: set() for uid in user_ids}
    for uid, ts in login_rows:
        usage_map[uid].add(ts.date())

    # --- Construcción de filas ---
    rows = []
    today = now.date()
    for u in page_obj.object_list:
        nombre = f"{u.first_name} {u.last_name}".strip() or "(sin nombre)"
        username = u.username

        if u.last_ts:
            last_seen_human = humanize_delta(now - u.last_ts)
            session_open = (u.last_event == SessionEvent.LOGIN)
        else:
            last_seen_human = humanize_delta(now - u.last_login) if u.last_login else "—"
            session_open = False

        used_dates = usage_map.get(u.id, set())
        usage_week = []
        for offset in range(6, -1, -1):  # hace 6 días ... hoy
            d = today - timedelta(days=offset)
            usage_week.append(d in used_dates)

        rows.append({
            "nombre": nombre,
            "username": username,
            "locations": "",  # pendiente de llenar
            "last_seen_human": last_seen_human,
            "usage_week": usage_week,
            "session_open": session_open,
        })

    return render(request, "monitoring/monitoring_view.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "page_size": page_size,
    })
