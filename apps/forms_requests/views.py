from django.contrib.auth.decorators import login_required, user_passes_test
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
from .models import ConstanciaGuarderia
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.forms_requests.models import ConstanciaGuarderia
from django.core.paginator import Paginator



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
        solicitudes = solicitudes.filter(pdf_respuesta__isnull=True)
    elif estado == 'completada':
        solicitudes = solicitudes.filter(pdf_respuesta__isnull=False)

    page_obj = Paginator(solicitudes, 20).get_page(request.GET.get('page'))

    return render(request, 'forms_requests/admin/request_form_admin.html', {
        'page_obj': page_obj,
        'q': q,
        'estado': estado
    })

#esta vista nos dirige a la plantilla de nuestro usuario
@login_required
def user_forms_view(request):
    template_name = 'forms_requests/user/request_form_user.html'
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    return render(request, template_name, {
        'dias_semana': dias_semana,
        'today': date.today()
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

    width, height = 842, 800
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Crear texto con estilo justificado
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

    # Definir un Frame donde poner el párrafo
    frame = Frame(70, 230, 480, 300, showBoundary=0)
    frame.addFromList([paragraph], c)

    # fecha
    c.setFont("Helvetica-Bold",  13)
    fecha_hoy = date.today().strftime("%d/%m/%Y")
    c.drawCentredString(440, 644, f"{fecha_hoy}")

    # Terminar el PDF temporal
    c.save()
    buffer.seek(0)

    # Fusionar con la plantilla PDF
    template_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'Constancia_laboral.pdf'
    )
    base_pdf = PdfReader(template_path)
    overlay_pdf = PdfReader(buffer)
    writer = PdfWriter()

    base_page = base_pdf.pages[0]
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    # Respuesta HTTP
    final_output = BytesIO()
    writer.write(final_output)
    final_output.seek(0)

    response = HttpResponse(final_output, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="constancia_laboral.pdf"'
    return response

#esta vista genera el pdf de la constancia especial
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

    width, height = 842, 800
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Crear texto con estilo justificado
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
        f"NSS: <b>{nss}</b><br/>"
        f"CURP: <b>{curp}</b><br/>"
        f"RFC: <b>{rfc}</b><br/><br/>"
        f"Se extiende la presente a petición del interesado, para los fines que él juzgue conveniente.<br/><br/>"
    )

    paragraph = Paragraph(texto, style)

    # Definir un Frame donde poner el párrafo
    frame = Frame(70, 230, 480, 300, showBoundary=0)
    frame.addFromList([paragraph], c)

    # fecha
    c.setFont("Helvetica-Bold",  13)
    fecha_hoy = date.today().strftime("%d/%m/%Y")
    c.drawCentredString(440, 644, f"{fecha_hoy}")

    # Terminar el PDF temporal
    c.save()
    buffer.seek(0)

    # Fusionar con la plantilla PDF
    template_path = os.path.join(
        settings.BASE_DIR, 'static', 'template', 'img', 'constancias', 'Constancia_especial.pdf'
    )
    base_pdf = PdfReader(template_path)
    overlay_pdf = PdfReader(buffer)
    writer = PdfWriter()

    base_page = base_pdf.pages[0]
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    # Respuesta HTTP
    final_output = BytesIO()
    writer.write(final_output)
    final_output.seek(0)

    response = HttpResponse(final_output, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="constancia_laboral.pdf"'
    return response


#esta vista nos ayuda a guardar en la base de datos las solicitudes de la guardería
@require_POST
@login_required
def guardar_constancia_guarderia(request):
    try:
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
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)