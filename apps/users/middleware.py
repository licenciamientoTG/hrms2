from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_paths = ('/change-password/', reverse('logout'))
        if (
            request.user.is_authenticated and
            hasattr(request.user, 'userprofile') and
            request.user.userprofile.must_change_password and
            request.path not in allowed_paths
        ):
            return redirect('force_password_change')  # nombre de la URL

        return self.get_response(request)
