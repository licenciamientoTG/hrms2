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
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

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
    if employee and employee.saving_fund:
        fondo_ahorro = int(employee.saving_fund)

    # --- LÓGICA DE TIEMPO ---
    today = date.today()
    current_week = today.isocalendar()[1]
    # current_week = 43  # <--- COMENTAR EN PRODUCCIÓN
    target_week = 44 
    
    if current_week > target_week:
        max_weeks_allowed = 10
    elif current_week == target_week:
        max_weeks_allowed = 0
    else:
        max_weeks_allowed = max(0, min(10, target_week - current_week))

    # --- LÓGICA DE CAPACIDAD DE PAGO (Regla del 30% del Bruto) ---
    capacidad_pago_semanal = 0
    
    # 30% del Bruto es el estándar seguro para deducir vía nómina
    # Esto deja el 70% restante para Impuestos (ISR/IMSS) y Gastos.
    PORCENTAJE_SEGURO = 0.30 

    if employee:
        sueldo_bruto_semanal = 0
        if hasattr(employee, 'daily_salary') and employee.daily_salary:
             sueldo_bruto_semanal = float(employee.daily_salary) * 7
        elif hasattr(employee, 'monthly_salary') and employee.monthly_salary:
             sueldo_bruto_semanal = (float(employee.monthly_salary) / 30) * 7
        
        capacidad_pago_semanal = sueldo_bruto_semanal * PORCENTAJE_SEGURO

    return render(
        request,
        "tools/user/calculator_user.html",
        {
            "fondo_ahorro": fondo_ahorro,
            "max_weeks_allowed": max_weeks_allowed,
            "sueldo_semanal": capacidad_pago_semanal,
            "current_week": current_week,
        },
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
        data = json.loads(request.body or "{}")

        try:
            monto = Decimal(str(data.get("amount", "0"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            semanas = int(data.get("weeks", 0))
        except:
            return JsonResponse({"ok": False, "error": "Datos inválidos."})

        # --- VALIDACIÓN DE TIEMPO ---
        today = date.today()
        current_week = today.isocalendar()[1] 
        # current_week = 43 # <--- COMENTAR EN PRODUCCIÓN
        target_week = 44
        
        if current_week > target_week:
            max_allowed = 10
        elif current_week == target_week:
            max_allowed = 0
        else:
            max_allowed = min(10, target_week - current_week)

        if max_allowed == 0:
             return JsonResponse({"ok": False, "error": "Semana de corte (44)."})
        if semanas > max_allowed:
            return JsonResponse({"ok": False, "error": f"Plazo máximo permitido: {max_allowed} semanas."})

        # Validaciones básicas
        if monto <= 0: return JsonResponse({"ok": False, "error": "Monto mayor a 0."})
        if semanas < 1: return JsonResponse({"ok": False, "error": "Mínimo 1 semana."})

        # Empleado
        employee = Employee.objects.filter(user=request.user).first()
        if not employee: return JsonResponse({"ok": False, "error": "Empleado no encontrado."})

        # ---------------------------------------------------------
        # BLOQUE DE CAPACIDAD (30% DEL BRUTO)
        # ---------------------------------------------------------
        limit_pago_semanal = Decimal("0.00")
        PORCENTAJE_SEGURO = Decimal("0.30") # 30% Estricto

        sueldo_bruto = Decimal("0.00")
        if hasattr(employee, 'daily_salary') and employee.daily_salary:
             sueldo_bruto = Decimal(str(employee.daily_salary)) * 7
        elif hasattr(employee, 'monthly_salary') and employee.monthly_salary:
             sueldo_bruto = (Decimal(str(employee.monthly_salary)) / 30) * 7
        
        # Calculamos el límite seguro
        limit_pago_semanal = sueldo_bruto * PORCENTAJE_SEGURO
        
        # Proyección
        pago_semanal_proyectado = monto / semanas
        
        # Validación
        if limit_pago_semanal > 0 and pago_semanal_proyectado > limit_pago_semanal:
            return JsonResponse({
                "ok": False, 
                "error": f"El pago semanal calculado (${pago_semanal_proyectado:,.2f}) es riesgoso para tu nivel salarial. "
                         f"Por política de seguridad financiera, tu descuento máximo permitido es de ${limit_pago_semanal:,.2f} semanales (30% de tu sueldo bruto)."
            })
        # ---------------------------------------------------------

        # Validar 50% Fondo
        ahorro_total = Decimal(str(employee.saving_fund or 0))
        limite_fondo = ahorro_total * Decimal("0.50")
        if monto > limite_fondo:
            return JsonResponse({"ok": False, "error": f"Excede el 50% de tu fondo (${limite_fondo:,.2f})."})

        # Validar Prestamo Activo
        ultimo = LoanRequest.objects.filter(user=request.user, status__in=["pending", "approved"]).order_by("-created_at").first()
        if ultimo:
            if ultimo.status == "pending": return JsonResponse({"ok": False, "error": "Solicitud en revisión."})
            if ultimo.status == "approved":
                fin = ultimo.created_at + timedelta(weeks=ultimo.weeks)
                if timezone.now() < fin:
                    return JsonResponse({"ok": False, "error": "Tienes un préstamo activo."})

        # Crear
        puesto = employee.job_position.title if employee.job_position else "Sin puesto"
        empresa = employee.company or "Sin empresa"
        num_empleado = employee.employee_number or ""
        nombre = f"{employee.first_name} {employee.last_name}".strip()
        pago_final = pago_semanal_proyectado.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        LoanRequest.objects.create(
            user=request.user,
            employee_number=num_empleado,
            full_name=nombre,
            job_position=puesto,
            company=empresa,
            saving_fund_snapshot=ahorro_total,
            amount=monto,
            weeks=semanas,
            payment_amount=pago_final,
            status="approved", 
        )

        return JsonResponse({"ok": True})

    except Exception:
        return JsonResponse({"ok": False, "error": "Error interno."})

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