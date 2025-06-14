from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from apps.courses import views
from .views import course_wizard, guardar_pregunta, user_courses, save_course, save_course_ajax, process_assignments
from .forms import CourseHeaderForm, CourseConfigForm, ModuleContentForm, LessonForm, QuizForm


urlpatterns = [
    path('course_wizard/', course_wizard, name='course_wizard'),
    path('user/courses/', user_courses, name='user_courses'),  # Vista para usuarios normales
    path('save_course', save_course, name='save_course'),
    path('api/save-course/', save_course_ajax, name='save_course_ajax'),
    path('process_assignments/', process_assignments, name='process_assignments'),
    path('segmentar-usuarios/<int:course_id>/', views.user_segmentation_view, name='segment_users'),
    path('run_assignments/<int:course_id>/', views.run_assignments, name='run_assignments'),
    path('my-courses/<int:course_id>/', views.view_course_content, name='view_course_content'), # Vista para los cursos del usuario
    path('admin/course/<int:course_id>/edit/', views.admin_course_edit, name='admin_course_edit'),  # Para admin
    path('wizard_form/', views.visual_course_wizard, name='visual_course_wizard'),
    path('guardar_pregunta/', views.guardar_pregunta, name='guardar_pregunta'),
    path('eliminar_pregunta/<int:question_id>/', views.eliminar_pregunta, name='eliminar_pregunta'),
    path('obtener-preguntas/<int:course_id>/', views.obtener_preguntas_curso, name='obtener_preguntas'),
    path('submit_course_quiz/<int:course_id>/', views.submit_course_quiz, name='submit_course_quiz'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)