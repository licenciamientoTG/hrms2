from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from departments.models import Department 

class CourseCategory(models.Model):
    title = models.CharField(
        max_length=200,
        help_text="Título de la categoría del curso.",
        verbose_name="Título",       
    )
    description = models.TextField(
        help_text=_("Descripción de la categoría del curso."),
        verbose_name=_("Descripción")
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        help_text="Usuario que creó la categoría.",
        verbose_name="Usuario"
    )
    updated_at = models.DateTimeField(
        auto_now=True, null=True,
        help_text="Fecha de última actualización.",
        verbose_name="Actualizado en"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de creación.",
        verbose_name="Creado en"
    )

    class Meta:
        verbose_name = "Categoría de curso"
        verbose_name_plural = "Categorías de cursos"

    def __str__(self):
        return self.title


class CourseHeader(models.Model):
    title = models.CharField(
        max_length=140,
        verbose_name="Título del curso:",
    )
    description = models.TextField(
        verbose_name="Descripción del curso:",
    )
    duration = models.FloatField(
        verbose_name="Duración del curso en horas:",
    )
    category = models.ForeignKey(
        CourseCategory, on_delete=models.CASCADE,
        verbose_name="Categoría del curso:",
    )
    portrait = models.ImageField(
        upload_to="courses/",
        verbose_name="Imagen del curso (JPG, PNG, GIF, 800x400px).",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        help_text="Usuario que creó el curso.",
        verbose_name="Usuario"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return self.title


class ModuleContent(models.Model):
    course_header = models.ForeignKey(
        CourseHeader, on_delete=models.CASCADE,
        help_text="Curso al que pertenece el módulo.",
        verbose_name="Curso"
    )
    title = models.CharField(
        max_length=140,
        help_text="Título del módulo.",
        verbose_name="Título"
    )
    description = models.TextField(
        help_text="Descripción del módulo.",
        verbose_name="Descripción"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"

    def __str__(self):
        return self.title


class Lesson(models.Model):
    LESSON_TYPES = [
        ("Video", "Video"),
        ("Lectura", "Lectura"),
        ("Articulo", "Artículo"),
        ("SCORM", "SCORM"),
    ]

    module_content = models.ForeignKey(
        ModuleContent, on_delete=models.CASCADE,
        help_text="Módulo al que pertenece la lección.",
        verbose_name="Módulo"
    )
    title = models.CharField(
        max_length=140,
        help_text="Título de la lección.",
        verbose_name="Título"
    )
    lesson_type = models.CharField(
        max_length=20, choices=LESSON_TYPES,
        help_text="Tipo de lección.",
        verbose_name="Tipo de lección"
    )
    description = models.TextField(
        help_text="Descripción de la lección.",
        verbose_name="Descripción"
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        help_text="Enlace de video opcional (por ejemplo, YouTube).",
        verbose_name="URL del video"
    )
    resource = models.FileField(
        upload_to="lessons/", blank=True, null=True,
        help_text="Archivo adjunto o enlace a un recurso externo.",
        verbose_name="Recurso"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lección"
        verbose_name_plural = "Lecciones"

    def __str__(self):
        return self.title


class LessonAttachment(models.Model):
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE,
        help_text="Lección a la que pertenece el archivo adjunto.",
        verbose_name="Lección"
    )
    file_link = models.URLField(
        help_text="Enlace al archivo adjunto.",
        verbose_name="Enlace del archivo"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Archivo adjunto"
        verbose_name_plural = "Archivos adjuntos"

    def __str__(self):
        return f"Adjunto para {self.lesson.title}"


class Quiz(models.Model):
    course_header = models.ForeignKey(
        CourseHeader, on_delete=models.CASCADE,
        verbose_name="Curso al que pertenece el cuestionario.",
    )
    title = models.CharField(
        max_length=140,
        verbose_name="Título del cuestionario.",
    )
    description = models.TextField(
        verbose_name="Descripción del cuestionario.",
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cuestionario"
        verbose_name_plural = "Cuestionarios"

    def __int__(self):
        return self.id


class Question(models.Model):
    QUESTION_TYPES = [
        ("Texto", "Texto"),
        ("Respuesta Unica", "Respuesta Única"),
        ("Respuesta Multiple", "Respuesta Múltiple"),
    ]

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE,
        help_text="Cuestionario al que pertenece la pregunta.",
        verbose_name="Cuestionario"
    )
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPES,
        help_text="Tipo de pregunta.",
        verbose_name="Tipo de pregunta"
    )
    question_text = models.CharField(
        max_length=200,
        help_text="Texto de la pregunta.",
        verbose_name="Pregunta"
    )
    explanation = models.TextField(
        null=True, blank=True,
        help_text="Explicación de la respuesta (opcional).",
        verbose_name="Explicación"
    )
    score = models.PositiveIntegerField(
        default=1, help_text="Puntaje que vale esta pregunta"
    )
    
    single_answer = models.TextField(
        null=True, blank=True,
        help_text="Respuesta única en caso de ser de tipo 'Texto'.",
        verbose_name="Respuesta única"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return self.question_text


class Answer(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE,
        help_text="Pregunta a la que pertenece la respuesta.",
        verbose_name="Pregunta"
    )
    answer_text = models.CharField(
        max_length=200,
        help_text="Texto de la respuesta.",
        verbose_name="Respuesta"
    )
    is_correct = models.BooleanField(
        default=False,
        help_text="Indica si la respuesta es correcta.",
        verbose_name="Es correcta"
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"

    def __str__(self):
        return self.answer_text
    
    
class QuizConfig(models.Model):
    quiz = models.OneToOneField(
        'Quiz',
        on_delete=models.CASCADE,
        related_name='config',
        verbose_name="Cuestionario"
    )
    passing_score = models.PositiveIntegerField(
        default=60, 
        help_text="Porcentaje mínimo para aprobar (0-100)"
    )
    max_attempts = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Número máximo de intentos (en blanco = sin límite)"
    )
    time_limit_minutes = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Límite de tiempo en minutos (opcional)"
    )
    show_correct_answers = models.BooleanField(
        default=True,
        help_text="Mostrar respuestas correctas al finalizar"
    )

    class Meta:
        verbose_name = "Configuración del Cuestionario"
        verbose_name_plural = "Configuraciones de Cuestionarios"

    def __str__(self):
        return f"Configuración de '{self.quiz.title}'"
        
class QuizAttempt(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey('Quiz', on_delete=models.CASCADE)
    course = models.ForeignKey('CourseHeader', on_delete=models.CASCADE)
    score = models.IntegerField()
    percentage = models.FloatField()
    passed = models.BooleanField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score} pts"


class EnrolledCourse(models.Model):
    """
    Tabla que relaciona los cursos asignados a cada usuario, registrando detalles como 
    la fecha de asignación, el estado del curso y otra información relevante.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="enrolled_courses",
        help_text="Usuario al que se le ha asignado el curso.",
        verbose_name="Usuario"
    )
    course = models.ForeignKey(
        CourseHeader,  # Ajustado a la estructura actual
        on_delete=models.CASCADE,
        related_name="enrolled_users",
        help_text="Curso al que está inscrito el usuario.",
        verbose_name="Curso"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora en la que el usuario fue asignado al curso.",
        verbose_name="Fecha de asignación"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('in_progress', 'En progreso'),
            ('completed', 'Completado'),
            ('failed', 'No aprobado'),
        ],
        default='pending',
        help_text="Estado actual del curso para este usuario.",
        verbose_name="Estado"
    )
    progress = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Porcentaje de progreso del usuario en el curso (0-100).",
        verbose_name="Progreso"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha en la que el usuario completó el curso (si aplica).",
        verbose_name="Fecha de finalización"
    )
    last_accessed = models.DateTimeField(
        null=True, blank=True,
        help_text="Última fecha en la que el usuario accedió al curso.",
        verbose_name="Último acceso"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notas adicionales sobre la inscripción del usuario en este curso.",
        verbose_name="Notas"
    )

    class Meta:
        verbose_name = "Curso Inscrito"
        verbose_name_plural = "Cursos Inscritos"
        db_table = "enrolled_course"
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.course.title} ({self.get_status_display()})"


class CourseAssignment(models.Model):
    """
    Modelo que gestiona la asignación de cursos a diferentes audiencias: 
    todos los usuarios, departamentos específicos o usuarios individuales.
    """
    ASSIGNMENT_TYPES = [
        ("all_users", "Todo el personal"),
        ("by_department", "Por departamento"),
        ("specific_users", "Usuarios específicos"),
    ]

    course = models.ForeignKey(
        CourseHeader,
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text="Curso que se está asignando.",
        verbose_name="Curso"
    )
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPES,
        default="all_users",
        help_text="Tipo de asignación del curso.",
        verbose_name="Tipo de asignación"
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        help_text="Departamentos a los que se asigna el curso.",
        verbose_name="Departamentos"
    )
    users = models.ManyToManyField(
        User,
        blank=True,
        help_text="Usuarios específicos a los que se asigna el curso.",
        verbose_name="Usuarios"
    )
        # Agrega estas nuevas relaciones ManyToMany
    positions = models.ManyToManyField(
        'employee.JobPosition',  # Asumiendo que JobPosition está en tu app employee
        blank=True,
        help_text="Posiciones laborales a las que se asigna el curso.",
        verbose_name="Posiciones"
    )
    locations = models.ManyToManyField(
        'location.Location',  # Asumiendo que Location está en tu app location
        blank=True,
        help_text="Ubicaciones físicas a las que se asigna el curso.",
        verbose_name="Ubicaciones"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_assignments",
        help_text="Usuario que asignó el curso.",
        verbose_name="Asignado por"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora de asignación.",
        verbose_name="Fecha de asignación"
    )

    class Meta:
        verbose_name = "Asignación de Curso"
        verbose_name_plural = "Asignaciones de Cursos"
        db_table = "course_assignment"

    def __str__(self):
        return f"{self.course.title} - {self.get_assignment_type_display()}"
    

class CourseConfig(models.Model):
    """
    Configuración de un curso, definiendo si es obligatorio u opcional,
    su secuencialidad, plazos, audiencia y certificación de finalización.
    """

    COURSE_TYPE_CHOICES = [
        ("mandatory", "Obligatorio"),
        ("optional", "Opcional"),
    ]

    AUDIENCE_CHOICES = [
        ("all_users", "Todos los usuarios"),
        ("segment", "Requiere segmentación"),
    ]

    course = models.OneToOneField(
        CourseHeader,
        on_delete=models.CASCADE,
        related_name="config",
        verbose_name="Curso"
    )
    course_type = models.CharField(
        max_length=10,
        choices=COURSE_TYPE_CHOICES,
        default="mandatory",
        verbose_name="Tipo de curso"
    )
    sequential = models.BooleanField(
        default=True,
        help_text="Indica si el curso debe completarse en orden secuencial.",
        verbose_name="Secuencialidad"
    )
    deadline = models.IntegerField(
        default=90,
        verbose_name="Plazo límite en días"
    )
    audience = models.CharField(
        max_length=15,
        choices=AUDIENCE_CHOICES,
        default="all_users",
        verbose_name="Audiencia"
    )
    certification = models.BooleanField(
        default=False,
        help_text="Indica si el usuario recibe un certificado al completar el curso.",
        verbose_name="Certificado de finalización"
    )
    requires_signature = models.BooleanField(
        default=False,
        help_text="Indica si el usuario debe firmar al completar el curso.",
        verbose_name="Requiere firma"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        help_text="Fecha de última actualización.",
        verbose_name="Fecha de actualización"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de creación de la configuración.",
        verbose_name="Fecha de creación"
    )

    class Meta:
        verbose_name = "Configuración del Curso"
        verbose_name_plural = "Configuraciones de Cursos"
        db_table = "course_config"

    def __str__(self):
        return f"Configuración de {self.course.title}"
    
 # models.py
class CourseCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(CourseHeader, on_delete=models.CASCADE)
    file = models.FileField(upload_to='certificates/')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')
        verbose_name = "Certificado de curso"
        verbose_name_plural = "Certificados de cursos"

    def __str__(self):
        return f"Certificado: {self.user.get_full_name()} - {self.course.title}"