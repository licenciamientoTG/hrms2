from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from apps.courses import views
from .views import course_wizard, user_courses, save_course, save_course_ajax, process_assignments
from .forms import CourseHeaderForm, CourseConfigForm, ModuleContentForm, LessonForm, QuizForm


urlpatterns = [
    path('course_wizard/', course_wizard, name='course_wizard'),
    path('user/courses/', user_courses, name='user_courses'),  # Vista para usuarios normales
    path('save_course', save_course, name='save_course'),
    path('api/save-course/', save_course_ajax, name='save_course_ajax'),
    path('process_assignments/', process_assignments, name='process_assignments'),
    path('segmentar-usuarios/<int:course_id>/', views.user_segmentation_view, name='segment_users'),
    path('run_assignments/<int:course_id>/', views.run_assignments, name='run_assignments'),
    

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)