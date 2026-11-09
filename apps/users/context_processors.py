from apps.users.models import LinkedAccount


def linked_account_context(request):
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    original_admin_id = request.session.get('original_admin_id')

    if original_admin_id:
        # Estamos en modo empleado, vinimos de un admin
        from django.contrib.auth.models import User
        admin_user = User.objects.filter(pk=original_admin_id).first()
        return {
            'switch_mode': 'back_to_admin',
            'switch_admin_user': admin_user,
        }

    # Verificar si el usuario actual (admin/staff) tiene una cuenta vinculada
    try:
        la = request.user.linked_account
        return {
            'switch_mode': 'to_employee',
            'switch_employee_user': la.employee_user,
        }
    except LinkedAccount.DoesNotExist:
        pass

    # Verificar si el usuario actual (empleado) tiene un admin vinculado
    try:
        la = request.user.linked_from_admin
        return {
            'switch_mode': 'back_to_admin',
            'switch_admin_user': la.admin_user,
        }
    except LinkedAccount.DoesNotExist:
        return {}
