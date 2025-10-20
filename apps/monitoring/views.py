from datetime import timedelta, datetime, timezone as dt_timezone
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Value

from apps.monitoring.models import SessionEvent, UserDailyUse
from django.conf import settings
from django.contrib.sessions.models import Session

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
    idle_threshold = now - timedelta(seconds=IDLE_SECONDS)

    # ---- SESSIONS ACTIVAS (middleware last_activity_ts) ----
    # Construimos: user_id -> última actividad y set de user_ids activos
    last_activity_map = {}
    active_ids = set()
    for s in Session.objects.filter(expire_date__gt=now):
        data = s.get_decoded()
        uid = data.get("_auth_user_id")
        ts  = data.get("last_activity_ts")
        if not uid or not ts:
            continue
        uid = int(uid)
        last_act = datetime.fromtimestamp(float(ts), dt_timezone.utc)
        prev = last_activity_map.get(uid)
        last_activity_map[uid] = max(prev, last_act) if prev else last_act
        if last_act >= idle_threshold:
            active_ids.add(uid)

    # ---- Subqueries para último evento (por si no hay session ts) ----
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
    last_login_city_sq = (
        SessionEvent.objects.filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts").values("city")[:1]
    )
    last_login_region_sq = (
        SessionEvent.objects.filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts").values("region")[:1]
    )
    last_login_country_sq = (
        SessionEvent.objects.filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts").values("country")[:1]
    )
    last_login_ip_sq = (
        SessionEvent.objects.filter(user_id=OuterRef("id"), event=SessionEvent.LOGIN)
        .order_by("-ts").values("ip")[:1]
    )

    # ---- Filtro de búsqueda ----
    q = (request.GET.get("q") or "").strip()
    users_qs = User.objects.only("id", "username", "first_name", "last_name", "last_login").filter(is_active=True)
    if q:
        for term in q.split():
            users_qs = users_qs.filter(
                Q(username__icontains=term) |
                Q(first_name__icontains=term) |
                Q(last_name__icontains=term)
            )

    # ---- Annotate y ORDEN ----
    # is_open = (id en sesiones activas) OR (último evento fue LOGIN y reciente)
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
                When(Q(id__in=list(active_ids)) |
                     (Q(last_event=SessionEvent.LOGIN) & Q(last_ts__gte=idle_threshold)),
                     then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            last_activity=Coalesce("last_ts", "last_login"),
        )
        .order_by("-is_open", "-last_activity", "id")
    )

    # --- Paginación (sin límite cuando hay búsqueda) ---
    page_size   = int(request.GET.get("page_size", 50))
    page_number = request.GET.get("page", 1)

    if q:
        # Sin paginación cuando hay término de búsqueda:
        page_obj = None
        users_iter = users_qs  # todos los que hacen match
        user_ids = list(users_qs.values_list("id", flat=True))
    else:
        paginator = Paginator(users_qs, page_size)
        page_obj = paginator.get_page(page_number)
        users_iter = page_obj.object_list
        user_ids = list(users_iter.values_list("id", flat=True))

    # --- USO ÚLTIMOS 7 DÍAS ---
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

    # --- Filas ---
    rows = []
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

    for u in users_iter:
        nombre = f"{u.first_name} {u.last_name}".strip() or "(sin nombre)"
        username = u.username

        ref_dt = last_activity_map.get(u.id) or u.last_activity
        last_seen_human = humanize_delta(now - ref_dt) if ref_dt else "—"
        session_open = bool(u.is_open)

        if u.last_city:
            last_place = u.last_city
        elif u.last_region:
            last_place = u.last_region
        elif u.last_country:
            last_place = u.last_country
        elif getattr(u, "last_ip", None):
            last_place = (
                f"Red interna ({u.last_ip})"
                if str(u.last_ip).startswith(("10.", "192.168.", "172."))
                else str(u.last_ip)
            )
        else:
            last_place = "—"

        used_dates = usage_map.get(u.id, set())
        week_cells = []
        for offset in range(6, -1, -1):
            d = today - timedelta(days=offset)
            used = d in used_dates
            base = "Hoy" if offset == 0 else ("Ayer" if offset == 1 else f"Hace {offset} días")
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
        "page_obj": page_obj,   # será None cuando hay q
        "q": q,
        "page_size": page_size,
    })
