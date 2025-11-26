from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from apps.users.views import force_password_change
from authapp.views import home   # 👈 importas la vista home desde authapp


urlpatterns = [
    path("admin/", admin.site.urls),

    # Login / Logout
    path("", auth_views.LoginView.as_view(
        template_name="authapp/login.html"
    ), name="login"),
    path("auth/login/", auth_views.LoginView.as_view(
        template_name="authapp/login.html"
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Home
    path("home/", home, name="home"),

    # Apps
    path("auth/", include("authapp.urls")),
    path("departments/", include("departments.urls")),
    path("news/", include("apps.news.urls")),
    path("forms_requests/", include("apps.forms_requests.urls")),
    path("vacations/", include("apps.vacations.urls")),
    path("performance/", include("apps.performance.urls")),
    path("org_chart/", include("apps.org_chart.urls")),
    path("courses/", include("apps.courses.urls")),
    path("users/", include("apps.users.urls")),
    path("recognitions/", include("apps.recognitions.urls")),
    path("objectives/", include("apps.objectives.urls")),
    path("archive/", include("apps.archive.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("surveys/", include("apps.surveys.urls")),
    path("documents/", include("apps.documents.urls")),
    path("job_offers/", include("apps.job_offers.urls")),
    path("policies/", include("apps.policies.urls")),
    path("career_plan/", include("apps.career_plan.urls")),
    path("tools/", include("apps.tools.urls")),

    # Password change forzado
    path("change-password/", force_password_change, name="force_password_change"),

    # Reset de contraseña (flujo estándar Django)
    path("password_reset/",
         auth_views.PasswordResetView.as_view(),
         name="password_reset"),
    path("password_reset_done/",
         auth_views.PasswordResetDoneView.as_view(),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),

    # Otros módulos
    path("endpoints/", include("apps.endpoints.urls")),
    path("requisiciones/", include("apps.staff_requisitions.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("monitoring/", include("apps.monitoring.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
