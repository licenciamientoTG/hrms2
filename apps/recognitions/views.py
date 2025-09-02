from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import RecognitionCategory
from .forms import RecognitionCategoryForm


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

class CategoryCreateView(LoginRequiredMixin, AdminOnlyMixin, CreateView):
    template_name = "recognitions/admin/recognition_category_create.html" # tu formulario
    form_class = RecognitionCategoryForm
    success_url = reverse_lazy("category_list")

class CategoryUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    template_name = "recognitions/admin/recognition_dashboard_create.html" # puedes reutilizarlo
    form_class = RecognitionCategoryForm
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