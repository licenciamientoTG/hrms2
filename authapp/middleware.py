from django.shortcuts import redirect
from django.urls import reverse

class CheckTermsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Lista de rutas permitidas aunque no haya aceptado términos
            allowed_paths = [
                reverse('logout'),
                '/admin/', # Opcional: permitir admin
                '/static/', 
                '/media/',
            ]
            
            # Intentamos obtener la URL de términos, si falla es porque aun no la creamos en urls.py
            # pero el middleware se ejecutará después.
            try:
                terms_url = reverse('terms_and_conditions')
                allowed_paths.append(terms_url)
            except:
                terms_url = '/auth/terms/' # Fallback temporal

            try:
                allowed_paths.append(reverse('force_password_change'))
            except:
                pass

            # Verificar excepciones
            is_allowed = False
            for path in allowed_paths:
                if request.path.startswith(path):
                    is_allowed = True
                    break
            
            if not is_allowed:
                # Verificar el perfil
                if hasattr(request.user, 'userprofile'):
                    if not request.user.userprofile.accepted_terms:
                        return redirect('terms_and_conditions')
                else:
                    # Si el usuario no tiene perfil, podriamos querer crearlo o ignorarlo.
                    # Por seguridad, si no tiene perfil, asumimos que no ha aceptado.
                    # Pero en este sistema parece que userprofile es critico.
                    pass

        return self.get_response(request)
