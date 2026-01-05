from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
from .models import LoanRequest
from apps.employee.models import Employee
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from datetime import date, timedelta, datetime, time
import io
import xlsxwriter
from django.http import HttpResponse
from django.utils import timezone

@login_required
def calculator_view(request):
    if request.user.is_staff:
        return redirect('calculator_admin')
    else:
        return redirect('calculator_user')

@login_required
def calculator_user(request):
    employee = Employee.objects.filter(user=request.user).first()

    fondo_ahorro = 0
    if employee and employee.saving_fund is not None:
        # lo pasamos como entero para el input number
        fondo_ahorro = int(employee.saving_fund)

    return render(
        request,
        "tools/user/calculator_user.html",
        {"fondo_ahorro": fondo_ahorro},
    )

@login_required
@user_passes_test(lambda u: u.is_staff)
def calculator_admin(request):
    q = (request.GET.get('q') or '').strip()
    
    # Recibimos cadenas con hora: "2025-12-10T15:30"
    f_ini_str = request.GET.get('fecha_inicio')
    f_fin_str = request.GET.get('fecha_fin')

    qs = LoanRequest.objects.select_related('user').order_by('-created_at')

    # Variables de filtrado
    start_aware = None
    end_aware = None

    # --- LÓGICA DE FECHAS CON HORA ---
    if f_ini_str:
        try:
            # 1. Parsear fecha Y hora (El input manda una 'T' en medio)
            naive_start = datetime.strptime(f_ini_str, "%Y-%m-%dT%H:%M")
            
            # 2. Convertir a Aware (Asigna tu zona horaria local automáticamente)
            start_aware = timezone.make_aware(naive_start)

            if f_fin_str:
                naive_end = datetime.strptime(f_fin_str, "%Y-%m-%dT%H:%M")
                end_aware = timezone.make_aware(naive_end)
            else:
                # Si no pone fin, buscamos hasta el final de ese mismo día
                naive_end = datetime.combine(naive_start.date(), time.max)
                end_aware = timezone.make_aware(naive_end)

        except ValueError:
            start_aware = None
            end_aware = None

    # --- CASO POR DEFECTO (Semana Actual completa) ---
    if not start_aware or not end_aware:
        now = timezone.localtime(timezone.now())
        lunes = now.date() - timedelta(days=now.weekday())
        domingo = lunes + timedelta(days=6)
        
        # Inicio: Lunes 00:00 | Fin: Domingo 23:59:59
        start_aware = timezone.make_aware(datetime.combine(lunes, time.min))
        end_aware = timezone.make_aware(datetime.combine(domingo, time.max))

    # --- FILTRAR ---
    qs = qs.filter(created_at__range=(start_aware, end_aware))

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(full_name__icontains=q) |
            Q(employee_number__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Datos para el título
    semana_num = start_aware.isocalendar()[1]
    periodo = end_aware.strftime("%m/%Y")

    context = {
        "solicitudes": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        # Devolvemos el objeto datetime Aware (Django lo formatea en el HTML)
        "fecha_inicio_filtro": start_aware,
        "fecha_fin_filtro": end_aware,
        
        "semana": semana_num,
        "fecha_inicio": timezone.localtime(start_aware).strftime("%d/%m/%Y %H:%M"),
        "fecha_fin": timezone.localtime(end_aware).strftime("%d/%m/%Y %H:%M"),
        "periodo": periodo,
    }

    return render(request, "tools/admin/calculator_admin.html", context)

@login_required
@require_POST
def create_loan_request(request):
    try:
        # 1. Leer datos enviados por el botón JS (solo monto y semanas)
        data = json.loads(request.body)
        monto = float(data.get('amount', 0))
        semanas = int(data.get('weeks', 0))

        # 2. Buscar datos del empleado en la BD
        employee = Employee.objects.filter(user=request.user).first()
        if not employee:
            return JsonResponse({'ok': False, 'error': 'No se encontró información de empleado para este usuario.'})

        # 3. Extraer valores del empleado (Ahorro, Puesto, Empresa)
        ahorro_total = float(employee.saving_fund or 0)
        puesto = str(employee.job_position) if employee.job_position else "Sin puesto"
        empresa = employee.company or "Sin empresa"
        num_empleado = employee.employee_number or ""
        nombre_completo = f"{employee.first_name} {employee.last_name}"

        # 4. Validaciones
        ultimo_prestamo = LoanRequest.objects.filter(
            user=request.user,
            status__in=['pending', 'approved'] # Ignoramos 'rejected' o 'paid'
        ).order_by('-created_at').first()

        if ultimo_prestamo:
            # Si está pendiente, no dejar pedir otro
            if ultimo_prestamo.status == 'pending':
                return JsonResponse({'ok': False, 'error': 'Ya tienes una solicitud en revisión. Espera a que sea aprobada o rechazada.'})
            
            # Si está aprobado, verificar si ya pasó el plazo
            if ultimo_prestamo.status == 'approved':
                # Calcular fecha de fin: Fecha Inicio + Semanas
                fecha_inicio = ultimo_prestamo.created_at
                semanas_plazo = ultimo_prestamo.weeks
                fecha_fin_estimada = fecha_inicio + timedelta(weeks=semanas_plazo)
                
                # Si HOY es antes de la fecha fin, sigue pagando
                if timezone.now() < fecha_fin_estimada:
                    dias_restantes = (fecha_fin_estimada - timezone.now()).days
                    return JsonResponse({
                        'ok': False, 
                        'error': f'Tienes un préstamo activo. Podrás solicitar otro en aproximadamente {dias_restantes} días.'
                    })

        # 5. Guardar la solicitud con TODOS los datos
        LoanRequest.objects.create(
            user=request.user,
            # Datos Snapshot (copia del momento)
            employee_number=num_empleado,
            full_name=nombre_completo,
            job_position=puesto,
            company=empresa,
            saving_fund_snapshot=ahorro_total,
            # Datos del préstamo
            amount=monto,
            weeks=semanas,
            payment_amount=monto / semanas, # Cálculo simple del pago
            status='approved'
        )

        return JsonResponse({'ok': True})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@user_passes_test(lambda u: u.is_staff)
def export_loans_excel(request):
    q = (request.GET.get('q') or '').strip()
    f_ini_str = request.GET.get('fecha_inicio')
    f_fin_str = request.GET.get('fecha_fin')

    qs = LoanRequest.objects.select_related('user').order_by('-created_at')

    start_aware = None
    end_aware = None

    # --- LÓGICA DE FECHAS CON HORA (Idéntica a calculator_admin) ---
    if f_ini_str:
        try:
            naive_start = datetime.strptime(f_ini_str, "%Y-%m-%dT%H:%M")
            start_aware = timezone.make_aware(naive_start)

            if f_fin_str:
                naive_end = datetime.strptime(f_fin_str, "%Y-%m-%dT%H:%M")
                end_aware = timezone.make_aware(naive_end)
            else:
                naive_end = datetime.combine(naive_start.date(), time.max)
                end_aware = timezone.make_aware(naive_end)
        except ValueError:
            start_aware = None
            end_aware = None

    if not start_aware or not end_aware:
        now = timezone.localtime(timezone.now())
        lunes = now.date() - timedelta(days=now.weekday())
        domingo = lunes + timedelta(days=6)
        start_aware = timezone.make_aware(datetime.combine(lunes, time.min))
        end_aware = timezone.make_aware(datetime.combine(domingo, time.max))
    
    # --- FILTRAR ---
    qs = qs.filter(created_at__range=(start_aware, end_aware))

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(full_name__icontains=q) |
            Q(employee_number__icontains=q)
        )
    
    total_prestamos = qs.aggregate(Sum('amount'))['amount__sum'] or 0

    # 2. Configurar Excel
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    semana_num = start_aware.isocalendar()[1]
    periodo = end_aware.strftime("%m/%Y")
    
    worksheet = workbook.add_worksheet(f"Semana {semana_num}")

    # --- Estilos ---
    header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#00B0F0', 'border': 1})
    money_fmt = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
    center_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
    text_fmt = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
    percent_fmt = workbook.add_format({'num_format': '0%', 'align': 'center', 'valign': 'vcenter', 'border': 1})
    date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy hh:mm AM/PM', 'align': 'center', 'border': 1}) # Formato con hora
    total_fmt = workbook.add_format({'num_format': '$#,##0.00', 'bold': True, 'bg_color': '#FFFF00', 'border': 1})
    sig_name_fmt = workbook.add_format({'bold': False, 'align': 'center', 'top': 1, 'font_size': 10})
    sig_title_fmt = workbook.add_format({'bold': False, 'align': 'center', 'font_size': 10})
    sig_action_fmt = workbook.add_format({'italic': True, 'align': 'center', 'font_size': 9})
    title_main_fmt = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_size': 12})
    title_sub_fmt = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_size': 11})

    # Títulos
    titulo_principal = f"SOLICITUDES DE PRESTAMO POR FONDO DE AHORRO SEM {semana_num:02d}"
    worksheet.merge_range('B2:D2', titulo_principal, title_main_fmt)

    local_start = timezone.localtime(start_aware)
    local_end = timezone.localtime(end_aware)
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    f_inicio_str = f"{local_start.day}/{meses[local_start.month-1]}/{local_start.year} {local_start.strftime('%H:%M')}"
    f_fin_str = f"{local_end.day}/{meses[local_end.month-1]}/{local_end.year} {local_end.strftime('%H:%M')}"
    
    subtitulo = f"Del {f_inicio_str} al {f_fin_str} (Aplicar en periodo {periodo})"
    worksheet.merge_range('B3:D3', subtitulo, title_sub_fmt)
    
    headers = ["", "# Empleado", "Nombre", "Puesto", "Ahorro Total", "50% ", "Préstamo", "% Autorizado", "Fecha de préstamo", "Plazos a cumplir", "Pago Semanal", "Patrón"]
    worksheet.write_row('A5', headers, header_fmt)

    worksheet.set_column('A:A', 5); worksheet.set_column('B:B', 12); worksheet.set_column('C:C', 35)
    worksheet.set_column('D:D', 20); worksheet.set_column('E:G', 15); worksheet.set_column('H:H', 12)
    worksheet.set_column('I:I', 20); worksheet.set_column('J:K', 15); worksheet.set_column('L:L', 20)

    row = 5
    for index, loan in enumerate(qs, start=1):
        worksheet.write(row, 0, index, center_fmt)
        worksheet.write(row, 1, loan.employee_number, center_fmt)
        worksheet.write(row, 2, loan.full_name, text_fmt)
        worksheet.write(row, 3, loan.job_position, text_fmt)
        worksheet.write(row, 4, loan.saving_fund_snapshot, money_fmt)
        worksheet.write(row, 5, loan.fifty_percent_limit, money_fmt)
        worksheet.write(row, 6, loan.amount, money_fmt)
        
        pct_real = 0
        if loan.saving_fund_snapshot > 0:
            pct_real = float(loan.amount) / float(loan.saving_fund_snapshot)
        worksheet.write(row, 7, pct_real, percent_fmt)
        
        # Convertir a hora local antes de escribir en Excel
        fecha_local = timezone.localtime(loan.created_at).replace(tzinfo=None) if loan.created_at else ""
        worksheet.write_datetime(row, 8, fecha_local, date_fmt)
        
        worksheet.write(row, 9, loan.weeks, center_fmt)
        worksheet.write(row, 10, loan.payment_amount, money_fmt)
        worksheet.write(row, 11, loan.company, text_fmt)
        row += 1

    worksheet.write(row, 6, total_prestamos, total_fmt)

    workbook.close()
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nombre_archivo = f"Prestamos_Semana_{semana_num}_{local_start.year}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    return response