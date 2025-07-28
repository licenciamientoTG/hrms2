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
    template_name = ('forms_requests/user/request_form_user.html' )
    return render(request, template_name)

@login_required
def generar_constancia_laboral(request):
    employee = Employee.objects.filter(user=request.user).first()
    nombre_usuario = request.user.get_full_name()
    empresa = "(EMPRESA)"
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
        alignment=4  # 4 = Justify
    )

    texto = (
        f"La empresa <b>{empresa}</b> hace de su conocimiento que el C. <b>{nombre_usuario}</b> "
        f"labora en esta empresa desde el <b>{fecha_inicio}</b>, desempeñando el puesto de <b>{puesto}</b>. <br/><br/>"
        f"Se extiende la presente a petición del interesado, para los fines que él juzgue conveniente."
    )

    paragraph = Paragraph(texto, style)

    # Definir un Frame donde poner el párrafo
    frame = Frame(70, 380, 480, 120, showBoundary=0)
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

