from django.contrib import admin
from .models import Department, Employee

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'department', 'supervisor')
    search_fields = ('name', 'position')
    list_filter = ('department',)
