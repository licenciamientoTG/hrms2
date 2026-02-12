from django.shortcuts import redirect
from django.urls import reverse

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
            
            # Intentar agregar rutas dinámicas
            try:
                allowed_paths.append(reverse('terms_and_conditions'))
            except:
                allowed_paths.append('/auth/terms/')

            try:
                # Ruta de cambio de contraseña debe ser permitida 
                # para que no se bloquee con los términos
                allowed_paths.append(reverse('force_password_change'))
            except:
                pass

            is_allowed = any(request.path.startswith(path) for path in allowed_paths)
            
            if not is_allowed:
                # 2. JERARQUÍA: Primero verificar cambio de contraseña
                profile = getattr(request.user, 'userprofile', None)
                
                # Si tiene perfil y debe cambiar contraseña, dejamos que otro 
                # middleware o la lógica de home lo mande allá. No bloqueamos aquí.
                if profile and profile.must_change_password:
                    return self.get_response(request)

                # 3. Validar Términos y Condiciones
                # Si no tiene perfil o no ha aceptado, mandarlo a términos
                if not profile or not profile.accepted_terms:
                    return redirect('terms_and_conditions')

        return self.get_response(request)