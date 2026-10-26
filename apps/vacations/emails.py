import calendar as cal_module
from datetime import date
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
]
DIAS_ES = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']


def _build_month_calendar(year, month, marked_dates):
    """Genera una tabla HTML de un mes con los días marcados en azul."""
    mc = cal_module.monthcalendar(year, month)
    rows = ''
    for week in mc:
        cells = ''
        for i, day in enumerate(week):
            if day == 0:
                cells += '<td style="padding:4px;"></td>'
            else:
                d = date(year, month, day)
                is_marked = d in marked_dates
                is_weekend = i >= 5
                if is_marked:
                    style = ('background:#1663d8;color:#fff;border-radius:50%;'
                             'width:28px;height:28px;line-height:28px;text-align:center;'
                             'font-weight:bold;display:inline-block;')
                    cells += f'<td style="padding:4px;text-align:center;"><span style="{style}">{day}</span></td>'
                elif is_weekend:
                    cells += f'<td style="padding:4px;text-align:center;color:#bbb;">{day}</td>'
                else:
                    cells += f'<td style="padding:4px;text-align:center;color:#374151;">{day}</td>'
        rows += f'<tr>{cells}</tr>'

    header = ''.join(
        f'<th style="padding:4px;font-family:Arial,Helvetica,sans-serif;font-size:11px;'
        f'color:#6b7280;font-weight:normal;text-align:center;">{d}</th>'
        for d in DIAS_ES
    )
    title = f'{MESES_ES[month]} {year}'
    return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0"
       style="margin:0 auto 16px auto;min-width:224px;">
  <tr>
    <th colspan="7" style="padding:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;
                            font-size:14px;color:#0f3b68;font-weight:bold;text-align:center;">
      {title}
    </th>
  </tr>
  <tr>{header}</tr>
  {rows}
</table>"""


def _build_calendars_html(fecha_list):
    """Genera los calendarios HTML para todas las fechas seleccionadas."""
    if not fecha_list:
        return ''
    marked = set(fecha_list)
    # Agrupar por mes
    meses = sorted({(d.year, d.month) for d in fecha_list})
    calendarios = ''.join(_build_month_calendar(y, m, marked) for y, m in meses)
    # Si hay más de un mes, mostrarlos en fila
    if len(meses) > 1:
        cols = ''.join(
            f'<td style="padding:0 12px;vertical-align:top;">{_build_month_calendar(y, m, marked)}</td>'
            for y, m in meses
        )
        calendarios = f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;"><tr>{cols}</tr></table>'
    return f"""
<div style="background:#f0f4ff;border-radius:6px;padding:16px;margin-bottom:24px;text-align:center;">
  {calendarios}
</div>"""


def send_vacation_request_email(lider_emp, nombre_empleado, tipo_solicitud, dates_display, fecha_list=None):
    """
    Envía un correo al líder notificándole que tiene una nueva solicitud pendiente.
    fecha_list: lista de objetos date con los días seleccionados (para mostrar el calendario).
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

    logo_url = f"{base}/static/template/img/logos/LOGOTIPO.png"
    calendar_html = _build_calendars_html(fecha_list or [])

    html_body = f"""<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background-color:#f6f8fa;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">
    Nueva solicitud de {tipo_solicitud} — {nombre_empleado}
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f6f8fa;padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0"
               style="background:#ffffff;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.08);">
          <!-- ENCABEZADO -->
          <tr>
            <td align="center" style="background:#0f3b68;padding:24px;border-top-left-radius:8px;border-top-right-radius:8px;">
              <img src="{logo_url}" alt="HRMS" width="140"
                   style="display:block;height:auto;border:0;">
            </td>
          </tr>
          <!-- CUERPO -->
          <tr>
            <td style="padding:28px 32px 8px 32px;">
              <h1 style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;
                         font-size:22px;color:#0f3b68;">
                Nueva solicitud de {tipo_solicitud}
              </h1>
              <p style="margin:0 0 20px 0;font-family:Arial,Helvetica,sans-serif;
                        font-size:16px;color:#374151;line-height:1.6;">
                <strong>{nombre_empleado}</strong> ha enviado una solicitud de
                <strong>{tipo_solicitud}</strong>.
              </p>
              {calendar_html}
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:24px;">
                <tr>
                  <td bgcolor="#1663d8" style="border-radius:6px;">
                    <a href="{url}"
                       style="display:inline-block;padding:12px 24px;font-family:Arial,Helvetica,sans-serif;
                              font-weight:600;font-size:15px;color:#ffffff;text-decoration:none;">
                      Ver solicitud →
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- PIE -->
          <tr>
            <td align="center" style="padding:20px 32px 24px 32px;border-top:1px solid #eef2f7;">
              <div style="color:#6b7280;font-family:Arial,Helvetica,sans-serif;font-size:12px;">
                Enviado por HRMS &bull; No respondas a este correo.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
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
