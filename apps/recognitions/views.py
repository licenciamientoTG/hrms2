from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import path

from .models import RecognitionCategory


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

    return render(request, 'recognitions/admin/recognition_dashboard_admin.html')

# esta vista es para el usuario
@login_required
def recognition_dashboard_user(request):

    return render(request, 'recognitions/user/recognition_dashboard_user.html')

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
            return redirect("category_list")  # lista

    return render(request, "recognitions/admin/recognition_category_create.html", ctx)


class CategoryUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    template_name = "recognitions/admin/recognition_dashboard_create.html" # puedes reutilizarlo
    model = RecognitionCategory
    success_url = reverse_lazy("category_list")

class CategoryDeleteView(LoginRequiredMixin, AdminOnlyMixin, DeleteView):
    template_name = "recognitions/category_confirm_delete.html"
    model = RecognitionCategory
    success_url = reverse_lazy("category_list")

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_toggle_active(request, pk):
    obj = get_object_or_404(RecognitionCategory, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    return redirect("category_list")