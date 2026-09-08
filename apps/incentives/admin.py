from django.contrib import admin
from apps.incentives.models import CategoriaECV, IndicadorECV


class IndicadorECVInline(admin.TabularInline):
    model = IndicadorECV
    extra = 0
    fields = ('orden', 'nombre', 'ponderacion', 'unidad', 'direccion',
              'umbral_minimo', 'umbral_objetivo', 'umbral_excelente')
    ordering = ('orden',)


@admin.register(CategoriaECV)
class CategoriaECVAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    inlines = [IndicadorECVInline]
