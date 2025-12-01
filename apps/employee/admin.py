from django.contrib import admin
from .models import Employee, JobPosition, JobCategory

# Register your models here.
admin.site.register(Employee)
admin.site.register(JobPosition)
admin.site.register(JobCategory)