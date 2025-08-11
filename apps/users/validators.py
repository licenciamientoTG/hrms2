import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomComplexityValidator:
    """
    Valida que la contraseña tenga al menos:
    - 8 caracteres de largo
    - un número
    - una letra mayúscula
    - un carácter especial
    """

    def validate(self, password, user=None):
        errors = []

        if len(password) < 8:
            errors.append(
                ValidationError(
                    _("La contraseña debe tener al menos 8 caracteres."),
                    code='password_too_short'
                )
            )
        if not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    _("La contraseña debe contener al menos un número."),
                    code='password_no_number'
                )
            )
        if not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    _("La contraseña debe contener al menos una letra mayúscula."),
                    code='password_no_upper'
                )
            )
        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
            errors.append(
                ValidationError(
                    _("La contraseña debe contener al menos un carácter especial."),
                    code='password_no_special'
                )
            )

        if errors:
            # Levantamos todos juntos
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Tu contraseña debe tener al menos 8 caracteres, incluir un número, "
            "una letra mayúscula y un carácter especial."
        )
