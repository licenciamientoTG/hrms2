from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

class CheckTermsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 1. Rutas excluidas para evitar bucles
            allowed_paths = [
                reverse('logout'),
                '/static/',
                '/media/',
                '/admin/',
            ]

            try:
                allowed_paths.append(reverse('terms_and_conditions'))
            except:
                allowed_paths.append('/auth/terms/')

            try:
                allowed_paths.append(reverse('checador_policy'))
            except:
                allowed_paths.append('/auth/checador/')

            try:
                allowed_paths.append(reverse('force_password_change'))
            except:
                pass

            is_allowed = any(request.path.startswith(path) for path in allowed_paths)

            if not is_allowed:
                profile = getattr(request.user, 'userprofile', None)

                # 2. Primero: cambio de contraseña pendiente
                if profile and profile.must_change_password:
                    return redirect('force_password_change')

                # 3. Términos y condiciones
                if not profile or not profile.accepted_terms:
                    return redirect('terms_and_conditions')

                # 4. Comunicado de checadores (solo puestos que aplican)
                hace_4_meses = timezone.now() - timedelta(days=120)
                fecha_referencia = profile.last_checador_policy_at or profile.accepted_checador_policy_at
                checador_vencido = (
                    not profile.accepted_checador_policy or
                    not fecha_referencia or
                    fecha_referencia < hace_4_meses
                )
                if checador_vencido:
                    from .views import usuario_requiere_checador
                    if usuario_requiere_checador(request.user):
                        return redirect('checador_policy')

        return self.get_response(request)