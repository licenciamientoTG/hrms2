from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def send_vacation_request_email(lider_emp, nombre_empleado, tipo_solicitud, dates_display):
    """
    Envía un correo al líder notificándole que tiene una nueva solicitud pendiente.
    Usa TEST_VACATION_EMAIL si está definido (para staging), o el corporate_email del líder.
    """
    test_email = getattr(settings, 'TEST_VACATION_EMAIL', '').strip()
    to_email = test_email or (lider_emp.corporate_email or '').strip()
    if not to_email:
        return False

    base = (getattr(settings, 'SITE_BASE_URL', '') or '').rstrip('/')
    url = f"{base}/vacations/gestion/"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    subject = f"Nueva solicitud de {tipo_solicitud} — {nombre_empleado}"

    text_body = (
        f"Hola,\n\n"
        f"{nombre_empleado} ha enviado una solicitud de {tipo_solicitud} "
        f"para las fechas: {dates_display}.\n\n"
        f"Ingresa al sistema para revisarla:\n{url}\n\n"
        f"Este es un mensaje automático, por favor no respondas a este correo."
    )

    html_body = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="color:#0d6efd;">Nueva solicitud de {tipo_solicitud}</h2>
  <p><strong>{nombre_empleado}</strong> ha enviado una solicitud de
  <strong>{tipo_solicitud}</strong> para las fechas: <strong>{dates_display}</strong>.</p>
  <p>Ingresa al sistema para revisarla y aprobarla o rechazarla:</p>
  <p>
    <a href="{url}"
       style="display:inline-block;padding:10px 20px;background:#0d6efd;color:#fff;
              text-decoration:none;border-radius:5px;">
      Ver solicitud
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin-top:30px;">
  <p style="font-size:12px;color:#999;">Mensaje automático — no respondas a este correo.</p>
</body>
</html>"""

    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"[Vacaciones] Error enviando correo al líder {to_email}: {e}")
        return False
