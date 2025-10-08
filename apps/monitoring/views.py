from datetime import timedelta
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q

from apps.monitoring.models import SessionEvent
from apps.monitoring.models import UserDailyUse   # <-- NEW
from django.conf import settings

IDLE_SECONDS = getattr(settings, "IDLE_TIMEOUT_SECONDS", 1800)

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

    # ---- Subqueries para último evento (global) ----
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

    # Última localización basada en ÚLTIMO LOGIN
    last_login_city_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts")
        .values("city")[:1]
    )
    last_login_region_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts")
        .values("region")[:1]
    )
    last_login_country_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts")
        .values("country")[:1]
    )
    last_login_ip_sq = (
        SessionEvent.objects
        .filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts")
        .values("ip")[:1]
    )

    # Filtro de búsqueda opcional
    q = (request.GET.get("q") or "").strip()
    users_qs = (
        User.objects.only("id", "username", "first_name", "last_name", "last_login")
        .filter(is_active=True)
    )
    if q:
        for term in q.split():
            users_qs = users_qs.filter(
                Q(username__icontains=term) |
                Q(first_name__icontains=term) |
                Q(last_name__icontains=term)
            )

    users_qs = (
        users_qs
        .annotate(
            last_ts=Subquery(last_ts_sq),
            last_event=Subquery(last_event_sq),
            last_city=Subquery(last_login_city_sq),
            last_region=Subquery(last_login_region_sq),
            last_country=Subquery(last_login_country_sq),
            last_ip=Subquery(last_login_ip_sq),
            is_open=Case(
                When(last_event=SessionEvent.LOGIN, then=1),
                default=0,
                output_field=IntegerField(),
            ),
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

    # --- USO ÚLTIMOS 7 DÍAS con UserDailyUse (hora local) ---  <-- NEW
    today = timezone.localdate()
    start = today - timedelta(days=6)

    uses = (
        UserDailyUse.objects
        .filter(user_id__in=user_ids, date__range=(start, today))
        .values_list("user_id", "date")
    )
    usage_map = {uid: set() for uid in user_ids}
    for uid, d in uses:
        usage_map[uid].add(d)

    # --- Construcción de filas ---
    rows = []
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

    for u in page_obj.object_list:
        nombre = f"{u.first_name} {u.last_name}".strip() or "(sin nombre)"
        username = u.username

        if u.last_ts:
            last_seen_human = humanize_delta(now - u.last_ts)
            if u.last_event == SessionEvent.LOGIN:
                session_open = (now - u.last_ts).total_seconds() <= IDLE_SECONDS
                session_expired = not session_open
            else:
                session_open = False
                session_expired = False
        else:
            last_seen_human = humanize_delta(now - u.last_login) if u.last_login else "—"
            session_open = False
            session_expired = False

        # Ubicación breve
        if u.last_city:
            last_place = u.last_city
        elif u.last_region:
            last_place = u.last_region
        elif u.last_country:
            last_place = u.last_country
        elif getattr(u, "last_ip", None):
            if str(u.last_ip).startswith(("10.", "192.168.", "172.")):
                last_place = f"Red interna ({u.last_ip})"
            else:
                last_place = str(u.last_ip)
        else:
            last_place = "—"

        used_dates = usage_map.get(u.id, set())
        week_cells = []
        for offset in range(6, -1, -1):  # 6..0  => hace 6 días ... hoy
            d = today - timedelta(days=offset)
            used = d in used_dates
            if offset == 0:
                base = "Hoy"
            elif offset == 1:
                base = "Ayer"
            else:
                base = f"Hace {offset} días"
            label = f"{base} • {dias[d.weekday()]} {d.strftime('%d/%m')}"
            week_cells.append({"used": used, "label": label})

        rows.append({
            "nombre": nombre,
            "username": username,
            "locations": last_place,
            "last_seen_human": last_seen_human,
            "usage_week": [c["used"] for c in week_cells],
            "week_cells": week_cells,
            "session_open": session_open,
        })

    return render(request, "monitoring/monitoring_view.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "page_size": page_size,
    })
