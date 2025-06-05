from django.shortcuts import render, redirect, get_object_or_404
from .models import Department
from .forms import DepartmentCreateForm, DepartmentUpdateForm
from django.contrib.auth.decorators import login_required

@login_required

def department_list(request):
    departments = Department.objects.all()
    return render(request, 'departments/department_list.html', {'departments': departments})

def department_create(request):
    if request.method == 'POST':
        form = DepartmentCreateForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('department_list')
    else:
        form = DepartmentCreateForm()
    return render(request, 'departments/department_form.html', {'form': form})

def department_update(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentUpdateForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            return redirect('department_list')
    else:
        form = DepartmentUpdateForm(instance=department)
    return render(request, 'departments/department_form.html', {'form': form})

def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        department.delete()
        return redirect('department_list')
    return render(request, 'departments/department_confirm_delete.html', {'department': department})

def home(request):
    departments = Department.objects.all()
    return render(request, 'home.html', {'departments': departments})

