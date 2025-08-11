from django.shortcuts import redirect

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated and
            hasattr(request.user, 'userprofile') and
            request.user.userprofile.must_change_password and
            request.path != '/change-password/'  # Ruta a tu vista de cambio
        ):
            return redirect('force_password_change')  # nombre de la URL

        return self.get_response(request)
