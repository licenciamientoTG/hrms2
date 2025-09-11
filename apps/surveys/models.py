# surveys/models.py
from django.conf import settings
from django.db import models

class Survey(models.Model):
    title = models.CharField(max_length=255, default="Encuesta sin título")
    is_active = models.BooleanField(default=False)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='surveys')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class SurveySection(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255, default="")
    order = models.PositiveIntegerField(default=1)
    # destino al terminar la sección: null -> siguiente sección
    go_to_section = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    submit_on_finish = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f"Sección {self.order}"

class SurveyQuestion(models.Model):
    TEXT = 'text'
    SINGLE = 'single'
    # (puedes agregar más tipos luego)
    TYPES = [(TEXT, 'Texto'), (SINGLE, 'Opción única')]

    section = models.ForeignKey(SurveySection, on_delete=models.CASCADE, related_name='questions')
    title = models.CharField(max_length=255, default="Pregunta")
    qtype = models.CharField(max_length=20, choices=TYPES, default=SINGLE)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
