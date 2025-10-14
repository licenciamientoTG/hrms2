from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import path
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponseForbidden
from .models import RecognitionCategory, Recognition, RecognitionComment, RecognitionMedia
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.utils.timezone import now
from django.utils.timesince import timesince
from .models import RecognitionLike
from django.contrib import messages
from django.db.models import Prefetch, Count, Exists, OuterRef, Q



# esta vista te redirige a las vistas de usuario y administrador
@login_required
def recognition_dashboard(request):
    if request.user.is_superuser:
        return redirect('recognition_dashboard_admin')
    else:
        return redirect('recognition_dashboard_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def recognition_dashboard_admin(request):
    # Query + orden
    qs = RecognitionCategory.objects.order_by('order', 'title')

    # Paginación (opcional – 20 por página)
    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "categories": page_obj.object_list,          # lo que tu tabla usa
        "page_obj": page_obj,                        # para controles de paginación
        "is_paginated": page_obj.has_other_pages(),
    }
    return render(request, "recognitions/admin/recognition_dashboard_admin.html", context)

# esta vista es para el usuario
User = get_user_model()

MAX_RECIPIENTS = 30
MAX_IMAGES_PER_POST = 10  # puedes ajustarlo
MAX_MB = 10               # MB

def _is_image_ok(f):
    return f.content_type.startswith('image/') and f.size <= MAX_MB * 1024 * 1024

@login_required
@require_http_methods(["GET", "POST"])
def recognition_dashboard_user(request):
    # ⬇️ Bloquea creación si no tiene permiso
    if request.method == "POST" and not request.user.has_perm('recognitions.add_recognition'):
        # Si viene por AJAX, responde 403 JSON; si no, redirige con mensaje
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        messages.error(request, "No tienes permiso para enviar reconocimientos.")
        return redirect('recognition_dashboard_user')

    if request.method == "POST":
        recipients_ids = request.POST.getlist('recipients')
        category_id    = request.POST.get('category')
        message        = (request.POST.get('message') or '').strip()
        files          = request.FILES.getlist('media')   # <-- CLAVE

        errors = []
        if not recipients_ids:
            errors.append(_("Debes seleccionar al menos un destinatario."))
        if len(recipients_ids) > MAX_RECIPIENTS:
            errors.append(_("Máximo %(n)s colaboradores.") % {'n': MAX_RECIPIENTS})

        category = None
        if not category_id:
            errors.append(_("Selecciona una categoría."))
        else:
            category = get_object_or_404(RecognitionCategory, pk=category_id, is_active=True)

        # Validación de imágenes
        if files:
            files = files[:MAX_IMAGES_PER_POST]  # límite opcional
            bad = [f.name for f in files if not _is_image_ok(f)]
            if bad:
                errors.append(_("Hay imágenes no válidas o mayores a %(n)s MB: %(lst)s") %
                              {"n": MAX_MB, "lst": ", ".join(bad)})

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # Crear reconocimiento
            rec = Recognition.objects.create(
                author=request.user,
                category=category,
                message=message,
            )

            # Destinatarios
            users = User.objects.filter(id__in=recipients_ids, is_active=True)
            rec.recipients.add(*users)

            # Guardar TODAS las imágenes
            for f in files:
                RecognitionMedia.objects.create(recognition=rec, file=f)

            messages.success(request, _("¡Reconocimiento publicado!"))
            return redirect('recognition_dashboard_user')

    # FEED (más recientes primero) + prefetch de media
    feed = (
        Recognition.objects
        .select_related('author', 'category')
        .annotate(
            like_count=Count('likes_rel', distinct=True),
            my_liked=Exists(
                RecognitionLike.objects.filter(recognition=OuterRef('pk'), user=request.user)
            ),
        )
        .prefetch_related(
            'recipients', 'media',
            Prefetch('comments', queryset=RecognitionComment.objects.select_related('author').order_by('created_at'))
        )
        .order_by('-created_at')
    )

    ctx = {
        # Estos dos solo se usan por el modal; el template puede ocultarlos con {% if perms.recognitions.add_recognition %}
        "people": User.objects.filter(is_active=True)
                              .exclude(id=request.user.id)
                              .order_by('first_name', 'last_name', 'username'),
        "categories": RecognitionCategory.objects.filter(is_active=True)
                                                .order_by('order', 'title'),
        "feed": feed,
    }
    return render(request, 'recognitions/user/recognition_dashboard_user.html', ctx)

class AdminOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

class CategoryListView(LoginRequiredMixin, AdminOnlyMixin, ListView):
    template_name = "recognitions/admin/recognition_dashboard_admin.html"   # tu tabla
    model = RecognitionCategory
    context_object_name = "categories"
    paginate_by = 20

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_create(request):
    ctx = {"errors": {}, "initial": {}}

    if request.method == "POST":
        # recoger datos
        title  = request.POST.get("title", "").strip()
        points = request.POST.get("points", "0").strip()
        color_hex = request.POST.get("color_hex", "#1E3361").strip()
        confetti_enabled = request.POST.get("confetti_enabled") == "on"
        show_points = request.POST.get("show_points") == "on"
        order = request.POST.get("order", "0").strip()
        is_active = request.POST.get("is_active") == "on"
        cover_image = request.FILES.get("cover_image")

        # guardar para repoblar en caso de error
        ctx["initial"] = {
            "title": title, "points": points, "color_hex": color_hex,
            "confetti_enabled": confetti_enabled, "show_points": show_points,
            "order": order, "is_active": is_active
        }

        # validaciones mínimas
        if not title:
            ctx["errors"]["title"] = "El nombre es obligatorio."
        try:
            points_int = int(points)
            if points_int < 0: raise ValueError
        except ValueError:
            ctx["errors"]["points"] = "Puntos debe ser un entero ≥ 0."
        try:
            order_int = int(order)
            if order_int < 0: raise ValueError
        except ValueError:
            ctx["errors"]["order"] = "Orden debe ser un entero ≥ 0."
        if not color_hex.startswith("#") or len(color_hex) != 7:
            ctx["errors"]["color_hex"] = "Usa un color en formato #RRGGBB."

        if not ctx["errors"]:
            obj = RecognitionCategory(
                title=title,
                points=points_int,
                color_hex=color_hex,
                confetti_enabled=confetti_enabled,
                show_points=show_points,
                order=order_int,
                is_active=is_active,
            )
            if cover_image:
                obj.cover_image = cover_image
            obj.save()
            return redirect("recognition_dashboard")  # lista

    return render(request, "recognitions/admin/recognition_category_create.html", ctx)


class CategoryUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    model = RecognitionCategory
    template_name = "recognitions/admin/recognition_category_edit.html" 
    fields = [
        "title", "color_hex",
        "confetti_enabled",
        "cover_image", "is_active",
    ]
    success_url = reverse_lazy("recognition_dashboard")  # o "recognition_dashboard_admin"

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_delete_post(request, pk):
    if request.method != "POST":
        return redirect("recognition_dashboard")
    obj = get_object_or_404(RecognitionCategory, pk=pk)
    try:
        obj.delete()
        messages.success(request, "Categoría eliminada.")
    except ProtectedError:
        messages.error(
            request,
            "No se puede eliminar porque ya fue utilizada. Puedes desactivarla para impedir su uso futuro."
        )
    return redirect("recognition_dashboard")

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
@require_POST
def category_toggle_active(request, pk):
    obj = get_object_or_404(RecognitionCategory, pk=pk)

    # Si viene desde el SweetAlert (cuando no se puede borrar), desactiva sí o sí
    force_deactivate = request.POST.get("force_deactivate") == "1"

    if force_deactivate:
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active"])
            messages.success(request, "Categoría desactivada.")
        else:
            # Ya estaba desactivada: no la actives por error
            messages.info(request, "La categoría ya estaba desactivada.")
    else:
        # Toggle normal (botón “Activar/Desactivar” del menú)
        obj.is_active = not obj.is_active
        obj.save(update_fields=["is_active"])
        messages.success(
            request,
            "Categoría activada." if obj.is_active else "Categoría desactivada."
        )

    return redirect("recognition_dashboard")

# Crear comentario
@login_required
@require_POST
def recognition_comment_create(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)
    body = (request.POST.get('body') or '').strip()
    if not body:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Texto vacío.'}, status=400)
        messages.error(request, 'El comentario no puede estar vacío.')
        return redirect('recognition_dashboard_user')

    c = RecognitionComment.objects.create(
        recognition=rec,
        author=request.user,
        body=body
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            "recognitions/user/_comment.html",   # ← tu parcial
            {"c": c, "request": request},
            request=request
        )
        count = rec.comments.count()
        return JsonResponse({'ok': True, 'html': html, 'count': count})

    return redirect('recognition_dashboard_user')

# Borrar comentario (autor o moderador con permiso delete)
@login_required
@require_http_methods(["POST"])
def recognition_comment_delete(request, pk, cid):
    c = get_object_or_404(RecognitionComment, pk=cid, recognition_id=pk)

    can_delete = (
        request.user == c.author or
        request.user.has_perm('recognitions.delete_recognitioncomment')  # 👈 permiso built-in
    )
    if not can_delete:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return HttpResponseForbidden("No autorizado")

    c.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        count = RecognitionComment.objects.filter(recognition_id=pk).count()
        return JsonResponse({"ok": True, "count": count})

    return redirect('recognition_dashboard_user')


# toggle
@login_required
@require_POST
def recognition_like_toggle(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)
    obj, created = RecognitionLike.objects.get_or_create(recognition=rec, user=request.user)
    liked = created
    if not created:
        obj.delete()
    count = RecognitionLike.objects.filter(recognition=rec).count()
    return JsonResponse({'ok': True, 'liked': liked, 'count': count})

# lista
# helpers
def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""

def _display_name(user) -> str:
    fn = _first_token(getattr(user, "first_name", ""))
    ln = _first_token(getattr(user, "last_name", ""))
    full = f"{fn} {ln}".strip()
    return full or user.get_username()

@login_required
@require_GET
def recognition_likes_list(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)

    # Usamos el modelo intermedio RecognitionLike
    qs = (RecognitionLike.objects
          .filter(recognition=rec)
          .select_related("user")
          .order_by("-created_at"))

    items = [{
        "name": _display_name(like.user),
        "liked_at": "",
    } for like in qs]

    return JsonResponse({
        "rec_id": rec.id,
        "title": (rec.message or "")[:60],
        "count": qs.count(),
        "items": items,
    })