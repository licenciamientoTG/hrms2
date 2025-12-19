from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Survey(models.Model):
    title = models.CharField(max_length=255, default="Encuesta sin título")
    is_active = models.BooleanField(default=False)

    # ⇩ vienen de tu settings localStorage
    is_anonymous = models.BooleanField(default=False)     # por defecto FALSO
    auto_message = models.TextField(blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='surveys'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        permissions = [
            ("Modulo_encuestas", "Acceso al Módulo de Encuestas"),
        ]

    def __str__(self):
        return self.title


class SurveySection(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255, default="")
    order = models.PositiveIntegerField(default=1)

    # destino al terminar la sección
    go_to_section = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )
    submit_on_finish = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f"Sección {self.order}"


class SurveyQuestion(models.Model):
    # Tipos soportados en tu builder (sin dropdown)
    TEXT     = 'text'
    INTEGER  = 'integer'
    DECIMAL  = 'decimal'
    SINGLE   = 'single'
    MULTIPLE = 'multiple'
    RATING   = 'rating'
    NONE     = 'none'
    ASSESSMENT = 'assessment'
    FRECUENCY  = 'frecuency'

    TYPES = [
        (TEXT, 'Texto'),
        (INTEGER, 'Número entero'),
        (DECIMAL, 'Número decimal'),
        (SINGLE, 'Opciones (selección única)'),
        (MULTIPLE, 'Opciones (selección múltiple)'),
        (RATING, 'Calificación'),
        (ASSESSMENT,'Evaluación'), 
        (FRECUENCY,'Frecuencia'),
        (NONE, 'Sin respuesta'),
    ]

    section = models.ForeignKey(SurveySection, on_delete=models.CASCADE, related_name='questions')
    title   = models.CharField(max_length=255, default="Pregunta")
    qtype   = models.CharField(max_length=20, choices=TYPES, default=SINGLE)
    required = models.BooleanField(default=False)
    order   = models.PositiveIntegerField(default=1)

    # Solo para rating (si lo usas)
    rating_max = models.PositiveSmallIntegerField(default=5)

    # Branching (solo aplica a SINGLE)
    branch_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class SurveyOption(models.Model):
    """Opciones para SINGLE/MULTIPLE + posible salto por opción (SINGLE)."""
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name='options')
    label    = models.CharField(max_length=255)
    order    = models.PositiveIntegerField(default=1)
    is_correct = models.BooleanField(default=False)

    # si la pregunta es SINGLE y tiene branching, esta opción puede saltar a sección
    branch_to_section = models.ForeignKey(
        SurveySection, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label


class SurveyAudience(models.Model):
    """Audiencia/segmentación equivalente a tu localStorage audience."""
    MODE_ALL = 'all'
    MODE_SEG = 'segmented'

    survey = models.OneToOneField(Survey, on_delete=models.CASCADE, related_name='audience')
    mode = models.CharField(max_length=12, choices=[(MODE_ALL, 'Todos'), (MODE_SEG, 'Segmentado')], default=MODE_ALL)

    # Guardamos filtros tal cual (ids de deptos/posiciones/ubicaciones)
    filters = models.JSONField(default=dict, blank=True)

    # Usuarios seleccionados explícitamente
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='survey_audiences')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Audiencia de "{self.survey}"'

User = settings.AUTH_USER_MODEL

class SurveyResponse(models.Model):
    """Una “sesión” de respuesta a una encuesta."""
    survey = models.ForeignKey('surveys.Survey', on_delete=models.PROTECT, related_name='responses')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_responses')
    # Si la encuesta es anónima, guarda user=None
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=[('submitted', 'Enviada'), ('draft', 'Borrador')], default='submitted')
    meta = models.JSONField(default=dict, blank=True)  # ip, user-agent, etc.
    # Snapshot opcional por si versionas encuestas
    survey_title = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        who = 'Anónimo' if not self.user else str(self.user)
        return f'Respuesta {self.id} · {self.survey} · {who}'


class SurveyAnswer(models.Model):
    """
    Respuesta a una pregunta.
    Usamos columnas “union” para cada tipo de dato y un JSON para extras.
    """
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey('surveys.SurveyQuestion', on_delete=models.PROTECT, related_name='answers')

    # Guardamos el tipo/título como snapshot para robustez si editas la encuesta después
    q_type = models.CharField(max_length=20)               # single/multiple/text/integer/decimal/rating/assessment/frecuency
    q_title = models.TextField()
    required = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    # Valores por tipo (rellenas UN campo según el tipo)
    value_text = models.TextField(null=True, blank=True)                   # text
    value_int = models.IntegerField(null=True, blank=True)                 # integer / rating
    value_decimal = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)  # decimal
    value_choice = models.IntegerField(null=True, blank=True)              # single/assessment/frecuency (índice 0..n)
    value_multi = models.JSONField(default=list, blank=True)               # multiple (lista de índices 0..n)

    # Snapshot de opciones para reporte consistente
    snapshot = models.JSONField(default=dict, blank=True)
    # p.ej: {"options": ["Sí","No","Tal vez"], "selected_labels": ["Sí"]}

    class Meta:
        unique_together = (('response', 'question'),)
        indexes = [
            models.Index(fields=['response']),
            models.Index(fields=['question']),
            models.Index(fields=['q_type']),
        ]

    def __str__(self):
        return f'Ans {self.id} · Q{self.question_id} ({self.q_type})'