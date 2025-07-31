from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from .forms import FormRequestForm
from io import BytesIO
from datetime import date
import os
from django.http import HttpResponse
from django.conf import settings
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from apps.employee.models import Employee 


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
    template_name = ('forms_requests/admin/request_form_admin.html')
    return render(request, template_name)

#esta vista nos dirige a la plantilla de nuestro usuario
@login_required
def user_forms_view(request):
    template_name = 'forms_requests/user/request_form_user.html'
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    return render(request, template_name, {
        'dias_semana': dias_semana
    })

#esta vista genera el pdf de la constancia laboral
@login_required
def generar_constancia_laboral(request):
    employee = Employee.objects.filter(user=request.user).first()
    nombre_usuario = request.user.get_full_name()
    empresa = "(EMPRESA)"
    departamento = "(DEPARTAMENTO)"
    equipo = "(EQUIPO)"
    fecha_inicio = employee.start_date.strftime("%d/%m/%Y") if employee and employee.start_date else "(FECHA DE INICIO)"
    puesto = str(employee.job_position) if employee and employee.job_position else "(PUESTO)"
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
    empresa = "(EMPRESA)"
    departamento = "(DEPARTAMENTO)"
    equipo = "(EQUIPO)"
    nss = employee.imss if employee and employee.imss else "(NSS)"
    salario =  "(SALARIO)"
    curp = employee.curp if employee and employee.curp else "(CURP)"
    rfc = employee.rfc if employee and employee.rfc else "(RFC)"

    fecha_inicio = employee.start_date.strftime("%d/%m/%Y") if employee and employee.start_date else "(FECHA DE INICIO)"
    puesto = str(employee.job_position) if employee and employee.job_position else "(PUESTO)"
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
        f"Salario: <b>{salario}</b><br/>"
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

#esta vista te redirige a la plantilla de requisision de personal
@login_required
def requisicion_personal_view(request):
    return render(request, 'forms_requests/user/requisicion_personal.html')