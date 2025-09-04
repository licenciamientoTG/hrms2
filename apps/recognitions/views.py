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
from .models import RecognitionCategory, Recognition


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
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMG_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}

def _is_image_ok(f):
    if not f:
        return True
    if f.size > MAX_IMAGE_BYTES:
        return False
    ct_ok = (f.content_type or '').startswith('image/')
    name = (f.name or '').lower()
    ext_ok = any(name.endswith(ext) for ext in IMG_EXTS)
    return ct_ok and ext_ok

@login_required
@require_http_methods(["GET", "POST"])
def recognition_dashboard_user(request):
    if request.method == "POST":
        recipients_ids = request.POST.getlist('recipients')  # ← IMPORTANTE
        category_id    = request.POST.get('category')
        message        = (request.POST.get('message') or '').strip()
        media          = request.FILES.get('media')

        # Validaciones
        errors = []
        if not recipients_ids:
            errors.append(_("Debes seleccionar al menos un destinatario."))
        if len(recipients_ids) > MAX_RECIPIENTS:
            errors.append(_("Máximo %(n)s colaboradores.") % {'n': MAX_RECIPIENTS})
        if not category_id:
            errors.append(_("Selecciona una categoría."))
        else:
            category = get_object_or_404(RecognitionCategory, pk=category_id, is_active=True)

        if media and not _is_image_ok(media):
            errors.append(_("La imagen no es válida o excede 10 MB."))

        # Si hay errores, vuelve al template con mensaje
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # Crear reconocimiento
            rec = Recognition.objects.create(
                author=request.user,
                category=category,
                message=message,
                image=media if media else None,
            )
            # Recipients
            users = User.objects.filter(id__in=recipients_ids)
            rec.recipients.add(*users)

            messages.success(request, _("¡Reconocimiento publicado!"))
            return redirect('recognition_dashboard_user')  # o al feed

    # GET o POST con errores → render
    ctx = {
        "people": User.objects.filter(is_active=True).order_by('first_name','last_name','username'),
        "categories": RecognitionCategory.objects.filter(is_active=True).order_by('order','title'),
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
    obj.delete()
    return redirect("recognition_dashboard")


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_toggle_active(request, pk):
    obj = get_object_or_404(RecognitionCategory, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    return redirect("recognition_dashboard")