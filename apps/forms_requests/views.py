from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.shortcuts import render, redirect
from .forms import FormRequestForm
from io import BytesIO
from datetime import date, datetime
import os
from django.http import HttpResponse
from django.conf import settings
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from apps.employee.models import Employee
from .models import ConstanciaGuarderia, SolicitudAutorizacion
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from apps.forms_requests.models import ConstanciaGuarderia
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from urllib.parse import quote
from django.views.decorators.clickjacking import xframe_options_exempt
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse
from apps.notifications.utils import notify
from django.contrib.contenttypes.models import ContentType
from itertools import islice
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm


#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def request_form_view(request):
    if request.user.is_superuser:
        return redirect('admin_forms')
    else:
        return redirect('user_forms')

#esta vista nos dirige a la plantilla de nuestro administrador
@user_passes_test(lambda u: u.is_superuser)
def admin_forms_view(request):
    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or '').strip()

    solicitudes = ConstanciaGuarderia.objects.select_related('empleado').order_by('-fecha_solicitud')

    if q:
        f = Q(empleado__first_name__icontains=q) | Q(empleado__last_name__icontains=q) | Q(nombre_menor__icontains=q)
        if q.isdigit():
            f |= Q(id=int(q))
        solicitudes = solicitudes.filter(f)

    if estado == 'pendiente':
        # pendientes = sin PDF y NO rechazadas
        ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
        rechazadas_ids = SolicitudAutorizacion.objects.filter(
            content_type=ct, estado='rechazado'
        ).values_list('object_id', flat=True)
        solicitudes = solicitudes.filter(
            Q(pdf_respuesta__isnull=True) | Q(pdf_respuesta='')
        ).exclude(id__in=rechazadas_ids)

    elif estado == 'completada':
        solicitudes = solicitudes.filter(~Q(pdf_respuesta__isnull=True), ~Q(pdf_respuesta=''))

    elif estado == 'rechazada':
        ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
        rechazadas_ids = SolicitudAutorizacion.objects.filter(
            content_type=ct, estado='rechazado'
        ).values_list('object_id', flat=True)
        solicitudes = solicitudes.filter(id__in=rechazadas_ids)

    page_obj = Paginator(solicitudes, 20).get_page(request.GET.get('page'))
    return render(request, 'forms_requests/admin/request_form_admin.html', {
        'page_obj': page_obj,
        'q': q,
        'estado': estado
    })


# esta vista nos dirige a la plantilla de nuestro usuario
@login_required
def user_forms_view(request):
    template_name = 'forms_requests/user/request_form_user.html'
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # Trae todas las solicitudes del usuario y dividimos por estado en Python
    todas = (ConstanciaGuarderia.objects
             .filter(empleado=request.user)
             .order_by('-fecha_solicitud'))

    # en progreso = pendientes (sin PDF y sin decisión final)
    pendientes = [s for s in todas if s.estado == 'en progreso']
    solicitud_pendiente = pendientes[0] if pendientes else None

    # terminadas = completadas (aprobadas) o rechazadas
    solicitudes_anteriores = [s for s in todas if s.estado in ('completada', 'rechazada')]

    return render(request, template_name, {
        'dias_semana': dias_semana,
        'today': date.today(),
        'solicitud_pendiente': solicitud_pendiente,
        'solicitudes_anteriores': solicitudes_anteriores,
    })

#esta vista genera el pdf de la constancia laboral
@login_required
def generar_constancia_laboral(request):
    employee = Employee.objects.filter(user=request.user).first()
    nombre_usuario = request.user.get_full_name()
    empresa = employee.company if employee and employee.company else "(EMPRESA)"
    departamento = employee.department.name if employee and employee.department else "(DEPARTAMENTO)"
    equipo = employee.team if employee and employee.team else "(EQUIPO)"
    fecha_inicio = employee.start_date.strftime("%d/%m/%Y") if employee and employee.start_date else "(FECHA DE INICIO)"
    puesto = employee.job_position.title if employee and employee.job_position else "(PUESTO)"
    fecha_hoy = date.today().strftime("%d/%m/%Y")

    # --- PDF base para conocer tamaño ---
    template_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'Constancia_laboral.pdf'
    )
    base_pdf = PdfReader(template_path)
    base_page = base_pdf.pages[0]
    PAGE_W = float(base_page.mediabox.width)
    PAGE_H = float(base_page.mediabox.height)

    # --- Canvas overlay del mismo tamaño ---
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(PAGE_W, PAGE_H))

    # Texto justificado
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        name='Justificado',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=18,
        alignment=4
    )
    texto = (
        f"<b>A quien corresponda:</b><br/><br/>"
        f"La empresa <b>{empresa}</b> hace de su conocimiento que el C. <b>{nombre_usuario}</b> "
        f"labora en esta empresa desde el <b>{fecha_inicio}</b>, desempeñando el puesto de <b>{puesto}</b> "
        f"en el departamento <b>{departamento}</b> y equipo <b>{equipo}</b>.<br/><br/>"
        f"Se extiende la presente a petición del interesado, para los fines que él juzgue conveniente."
    )
    paragraph = Paragraph(texto, style)
    Frame(70, 230, 480, 300, showBoundary=0).addFromList([paragraph], c)

    # Fecha
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(440, 644, fecha_hoy)

    # --- Sello digital (junto a la firma) ---
    sello_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'SelloRFC.png'
    )
    if os.path.exists(sello_path):
        sello = ImageReader(sello_path)
        img_w_px, img_h_px = sello.getSize()

        # tamaño del sello
        STAMP_W = 38 * mm               # ancho del sello (ajústalo si lo ves grande/pequeño)
        scale   = STAMP_W / float(img_w_px)
        STAMP_H = img_h_px * scale

        # ====== POSICIÓN CERCA DE LA FIRMA ======
        # Ancla aproximada al área de la firma en tu plantilla (ajústalo una vez)
        SIGN_X = PAGE_W * 0.66          # más pequeño = más a la izquierda
        SIGN_Y = PAGE_H * 0.18         # más grande = más arriba

        # Desplazamientos finos desde el ancla para “pegarlo” al lado de la firma
        OFFSET_X = -10 * mm             # negativo = más a la izquierda del ancla
        OFFSET_Y = +6  * mm             # positivo = más arriba del ancla

        STAMP_X = SIGN_X + OFFSET_X
        STAMP_Y = SIGN_Y + OFFSET_Y
        # ========================================

        ANGLE = -12  # negativo = lado derecho ligeramente más abajo
        c.saveState()
        c.translate(STAMP_X, STAMP_Y)   # rota alrededor de la esquina inf-izq del sello
        c.rotate(ANGLE)
        c.drawImage(
            sello, 0, 0,
            width=STAMP_W, height=STAMP_H,
            preserveAspectRatio=True, mask='auto'
        )
        c.restoreState()
    else:
        c.setFont("Helvetica", 8)
        c.drawString(40, 40, "Sello no encontrado: SelloRFC.png")

    # Cerrar overlay y reposicionar buffer
    c.save()
    overlay_buffer.seek(0)

    # Mezclar overlay con plantilla
    overlay_pdf = PdfReader(overlay_buffer)
    writer = PdfWriter()
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    # Respuesta
    final_output = BytesIO()
    writer.write(final_output)
    final_output.seek(0)

    response = HttpResponse(final_output, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="constancia_laboral.pdf"'
    return response

@login_required
def validar_empleado_numero(request):
    num = (request.GET.get('num') or '').strip()
    if not num:
        return JsonResponse({"exists": False})

    qs = Employee._base_manager.select_related('user')  # incluye inactivos y sin user
    try:
        e = qs.get(employee_number=num)
    except MultipleObjectsReturned:
        e = qs.filter(employee_number=num).order_by('-id').first()
        if not e:
            return JsonResponse({"exists": False})
    except Employee.DoesNotExist:
        return JsonResponse({"exists": False})

    user_obj = getattr(e, 'user', None)

    # Construye nombre sin depender de que exista user
    nombre = (
        (user_obj.get_full_name() if user_obj and hasattr(user_obj, "get_full_name") else "")
        or f"{(getattr(e, 'first_name', '') or '').strip()} {(getattr(e, 'last_name', '') or '').strip()}".strip()
        or (user_obj.username if user_obj and getattr(user_obj, "username", None) else "")
        or (getattr(e, 'email', None) or f"Empleado {e.employee_number}")
    )

    # banderas útiles para el front (opcionales)
    emp_activo = getattr(e, 'is_active', None)
    user_activo = (user_obj.is_active if user_obj and hasattr(user_obj, "is_active") else None)

    return JsonResponse({
        "exists": True,
        "id": e.id,
        "name": nombre,
        "active": bool(emp_activo) if emp_activo is not None else None,
        "user_active": bool(user_activo) if user_activo is not None else None,
    })

# --- PDF: generar carta de recomendación (activos + inactivos) ---
@xframe_options_exempt  # necesario si lo cargas en <iframe>
@user_passes_test(lambda u: u.is_staff or u.is_superuser)  # solo admins
@login_required
def generar_carta_recomendacion(request):
    emp_num = (request.GET.get("employee_number") or "").strip()
    if not emp_num:
        raise Http404("Falta employee_number")

    # Usa _base_manager para no filtrar inactivos
    employee = get_object_or_404(
        Employee._base_manager.select_related("user", "department", "job_position"),
        employee_number=emp_num
    )

    user_obj = getattr(employee, "user", None)
    nombre = (
        f"{(employee.first_name or '').strip()} {(employee.last_name or '').strip()}".strip()
        or (user_obj.get_full_name() if user_obj and hasattr(user_obj, "get_full_name") else "")
        or (user_obj.username if user_obj and getattr(user_obj, "username", None) else "")
        or (employee.email or f"Empleado {employee.employee_number}")
    )
    empresa = employee.company or "(EMPRESA)"
    puesto = employee.job_position.title if employee.job_position else "(PUESTO)"
    departamento = employee.department.name if employee.department else "(DEPARTAMENTO)"
    fecha_inicio = employee.start_date.strftime("%d/%m/%Y") if employee.start_date else "(FECHA DE INICIO)"
    fecha_termino = (employee.termination_date.strftime("%d/%m/%Y") if employee.termination_date else "(FECHA DE TERMINO)")

    fecha_hoy = date.today().strftime("%d/%m/%Y")

    # Verifica que exista la plantilla
    template_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'Carta_recomendacion.pdf'
    )
    if not os.path.exists(template_path):
        raise Http404("Plantilla de carta no encontrada")

    # --- Generar overlay con ReportLab ---
    width, height = 842, 800  # ajusta a tu plantilla real (o usa A4 si corresponde)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        name='Justificado',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12.5,
        leading=18,
        alignment=4,  # justify
    )

    texto = (
        f"<b>A quien corresponda:</b><br/><br/>"
        f"Por medio de la presente, hacemos constar que <b>{nombre}</b> laboró en <b>{empresa}</b> "
        f"en el puesto de <b>{puesto}</b>, dentro del departamento de <b>{departamento}</b>. "
        f"Inició labores el <b>{fecha_inicio}</b> y concluyó el <b>{fecha_termino}</b>."
        f"<br/><br/>"
        f"Extendemos la presente carta a solicitud del interesado, para los fines que considere convenientes."
    )

    Frame(70, 250, 500, 320, showBoundary=0).addFromList([Paragraph(texto, style)], c)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(440, 644, fecha_hoy)
    c.save()
    buffer.seek(0)

    # --- Fusionar con plantilla base ---
    base_pdf = PdfReader(template_path)
    overlay_pdf = PdfReader(buffer)
    writer = PdfWriter()

    base_page = base_pdf.pages[0]
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    final_output = BytesIO()
    writer.write(final_output)
    final_output.seek(0)

    filename = f'carta_recomendacion_{employee.employee_number}.pdf'
    response = HttpResponse(final_output, content_type='application/pdf')
    response['Content-Disposition'] = (
        'attachment' if request.GET.get('dl') == '1' else 'inline'
    ) + f'; filename="{filename}"'
    # anti-caché (opcional pero recomendado)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


# esta vista genera el pdf de la constancia especial
@login_required
def generar_constancia_especial(request):
    employee = Employee.objects.filter(user=request.user).first()
    nombre_usuario = request.user.get_full_name()
    empresa = employee.company if employee and employee.company else "(EMPRESA)"
    departamento = employee.department.name if employee and employee.department else "(DEPARTAMENTO)"
    equipo = employee.team if employee and employee.team else "(EQUIPO)"
    nss = employee.imss if employee and employee.imss else "(NSS)"
    curp = employee.curp if employee and employee.curp else "(CURP)"
    rfc = employee.rfc if employee and employee.rfc else "(RFC)"
    fecha_inicio = employee.start_date.strftime("%d/%m/%Y") if employee and employee.start_date else "(FECHA DE INICIO)"
    puesto = employee.job_position.title if employee and employee.job_position else "(PUESTO)"
    fecha_hoy = date.today().strftime("%d/%m/%Y")

    # --- PDF base (plantilla) -> para obtener tamaño de página ---
    template_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'Constancia_especial.pdf'
    )
    base_pdf = PdfReader(template_path)
    base_page = base_pdf.pages[0]
    PAGE_W = float(base_page.mediabox.width)
    PAGE_H = float(base_page.mediabox.height)

    # --- Canvas overlay del mismo tamaño ---
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(PAGE_W, PAGE_H))

    # --- Texto justificado ---
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        name='Justificado',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=18,
        alignment=4  # TA_JUSTIFY
    )

    texto = (
        f"<b>A quien corresponda:</b><br/><br/>"
        f"La empresa <b>{empresa}</b> hace de su conocimiento que el C. <b>{nombre_usuario}</b> "
        f"labora en esta empresa desde el <b>{fecha_inicio}</b>, desempeñando el puesto de <b>{puesto}</b> "
        f"en el departamento <b>{departamento}</b> y equipo <b>{equipo}</b>.<br/><br/>"
        f"NSS: <b>{nss}</b><br/>"
        f"CURP: <b>{curp}</b><br/>"
        f"RFC: <b>{rfc}</b><br/><br/>"
        f"Se extiende la presente a petición del interesado, para los fines que él juzgue conveniente."
    )
    paragraph = Paragraph(texto, style)
    Frame(70, 230, 480, 300, showBoundary=0).addFromList([paragraph], c)

    # --- Fecha ---
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(440, 658, fecha_hoy)

    # --- Sello digital (rotado y al lado de la firma) ---
    sello_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'SelloRFC.png'
    )
    if os.path.exists(sello_path):
        sello = ImageReader(sello_path)
        img_w_px, img_h_px = sello.getSize()

        # Tamaño del sello
        STAMP_W = 38 * mm          # ajusta el ancho si lo quieres más grande/pequeño
        scale   = STAMP_W / float(img_w_px)
        STAMP_H = img_h_px * scale

        # === Ancla aproximada a la zona de la firma (ajústala una sola vez) ===
        # Usa proporciones del tamaño de la página para que sea independiente de px
        SIGN_X = PAGE_W * 0.66      # menor -> más a la izquierda
        SIGN_Y = PAGE_H * 0.13      # mayor -> más arriba

        # Ajustes finos respecto al ancla para “pegarlo” al lado de la firma
        OFFSET_X = -12 * mm         # negativo -> más a la izquierda
        OFFSET_Y = +5  * mm         # positivo -> más arriba

        STAMP_X = SIGN_X + OFFSET_X
        STAMP_Y = SIGN_Y + OFFSET_Y

        ANGLE = -12                 # giro horario: lado derecho queda un poco más abajo
        c.saveState()
        c.translate(STAMP_X, STAMP_Y)   # el origen pasa a la esquina inferior izquierda del sello
        c.rotate(ANGLE)
        c.drawImage(
            sello, 0, 0,
            width=STAMP_W, height=STAMP_H,
            preserveAspectRatio=True, mask='auto'
        )
        c.restoreState()
    else:
        c.setFont("Helvetica", 8)
        c.drawString(40, 40, "Sello no encontrado: SelloRFC.png")

    # --- Cerrar overlay ---
    c.save()
    overlay_buffer.seek(0)

    # --- Mezclar overlay con plantilla ---
    overlay_pdf = PdfReader(overlay_buffer)
    writer = PdfWriter()
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    # --- Respuesta HTTP ---
    final_output = BytesIO()
    writer.write(final_output)
    final_output.seek(0)

    response = HttpResponse(final_output, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="constancia_especial.pdf"'
    return response

#esta vista nos ayuda a guardar en la base de datos las solicitudes de la guardería
@require_POST
@login_required
def guardar_constancia_guarderia(request):
    try:
        ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
        rechazadas_ids = SolicitudAutorizacion.objects.filter(
            content_type=ct, estado='rechazado'
        ).values_list('object_id', flat=True)

        ya_pendiente = ConstanciaGuarderia.objects.filter(
            empleado=request.user
        ).exclude(id__in=rechazadas_ids).filter(
            Q(pdf_respuesta__isnull=True) | Q(pdf_respuesta='')
        ).exists()

        if ya_pendiente:
            return JsonResponse({
                "success": False,
                "error": "Ya tienes una solicitud en proceso. Espera la respuesta antes de enviar otra."
            }, status=400)
            
        # días → "Lunes,Martes,..."
        dias = request.POST.getlist("dias_laborales")
        dias_str = ",".join(dias)

        # parseo de fecha/hora del POST
        nacimiento_str = request.POST.get("nacimiento_menor")  # 'YYYY-MM-DD'
        hora_entrada_str = request.POST.get("hora_entrada")    # 'HH:MM'
        hora_salida_str  = request.POST.get("hora_salida")     # 'HH:MM'

        nacimiento = datetime.strptime(nacimiento_str, "%Y-%m-%d").date()
        hora_entrada = datetime.strptime(hora_entrada_str, "%H:%M").time()
        hora_salida  = datetime.strptime(hora_salida_str, "%H:%M").time()

        ConstanciaGuarderia.objects.create(
            empleado=request.user,
            dias_laborales=dias_str,
            hora_entrada=hora_entrada,
            hora_salida=hora_salida,
            nombre_guarderia=request.POST.get("nombre_guarderia"),
            direccion_guarderia=request.POST.get("direccion_guarderia"),
            nombre_menor=request.POST.get("nombre_menor"),
            nacimiento_menor=nacimiento,
        )
        return JsonResponse(
            {"success": True, "message": "Solicitud enviada correctamente."}
        ) 
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

#vista para ver los detalles de las solicitudes de guardería
@login_required
def guarderia_detalle(request, pk):
    obj = get_object_or_404(ConstanciaGuarderia, pk=pk)

    # seguridad: solo el dueño o un admin pueden ver
    if not request.user.is_superuser and obj.empleado_id != request.user.id:
        raise Http404()

    data = {
        "id": obj.id,
        "empleado": obj.empleado.get_full_name() or obj.empleado.username,
        "fecha_solicitud": obj.fecha_solicitud.strftime("%d/%m/%Y %H:%M") if obj.fecha_solicitud else "",
        "dias_laborales": obj.dias_laborales.split(",") if obj.dias_laborales else [],
        "hora_entrada": obj.hora_entrada.strftime("%H:%M") if obj.hora_entrada else "",
        "hora_salida": obj.hora_salida.strftime("%H:%M") if obj.hora_salida else "",
        "nombre_guarderia": obj.nombre_guarderia,
        "direccion_guarderia": obj.direccion_guarderia,
        "nombre_menor": obj.nombre_menor,
        "nacimiento_menor": obj.nacimiento_menor.strftime("%d/%m/%Y") if obj.nacimiento_menor else "",
        "estado": obj.estado,
        "pdf_url": obj.pdf_respuesta.url if getattr(obj.pdf_respuesta, "name", "") else None,
    }
    return JsonResponse({"ok": True, "solicitud": data})

# vista para responder la constancia de guardería
@login_required
@permission_required('forms_requests.change_constanciaguarderia', raise_exception=True)
def responder_guarderia(request, pk: int):
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    obj = get_object_or_404(ConstanciaGuarderia, pk=pk)

    f = request.FILES.get('pdf_respuesta')
    if not f:
        return JsonResponse({"ok": False, "error": "Adjunta un PDF."}, status=400)
    if not f.name.lower().endswith('.pdf'):
        return JsonResponse({"ok": False, "error": "El archivo debe ser PDF."}, status=400)

    obj.pdf_respuesta = f
    obj.respondido_por = request.user
    obj.respondido_at = timezone.now()
    obj.save(update_fields=['pdf_respuesta', 'respondido_por', 'respondido_at'])

    # >>> registrar la aprobación <<<
    ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
    SolicitudAutorizacion.objects.update_or_create(
        content_type=ct,
        object_id=obj.id,
        usuario=request.user,
        defaults={
            'estado': 'aprobado',
            'comentario': '',
            'fecha_revision': timezone.now(),
        }
    )

    pdf_url = request.build_absolute_uri(obj.pdf_respuesta.url) if getattr(obj.pdf_respuesta, 'url', None) else None
    return JsonResponse({"ok": True, "id": obj.id, "pdf_url": pdf_url})

@login_required
@permission_required('forms_requests.change_constanciaguarderia', raise_exception=True)
@require_POST
def rechazar_guarderia(request, pk: int):
    obj = get_object_or_404(ConstanciaGuarderia, pk=pk)

    comentario = (request.POST.get('comentario') or "").strip()

    # Creamos/actualizamos una SolicitudAutorizacion como "rechazado"
    ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
    sa, _ = SolicitudAutorizacion.objects.get_or_create(
        content_type=ct,
        object_id=obj.id,
        usuario=request.user,
        defaults={
            'estado': 'rechazado',
            'comentario': comentario,
            'fecha_revision': timezone.now()
        }
    )
    if sa.estado != 'rechazado' or sa.comentario != comentario:
        sa.estado = 'rechazado'
        sa.comentario = comentario
        sa.fecha_revision = timezone.now()
        sa.save(update_fields=['estado', 'comentario', 'fecha_revision'])

    # Notifica al empleado (opcional pero útil)
    try:
        from apps.notifications.utils import notify
        url = request.build_absolute_uri(reverse('forms_requests:user_forms'))
        notify(
            obj.empleado,
            "Solicitud de guardería rechazada",
            comentario or "Tu solicitud fue rechazada.",
            url,
            dedupe_key=f"guarderia-{obj.pk}-rechazada"
        )
    except Exception:
        pass

    return JsonResponse({"ok": True})