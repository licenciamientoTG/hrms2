from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q



# esta vista te redirige a las vistas de usuario y administrador
@login_required
def vacation_dashboard(request):
    if request.user.is_superuser:
        return redirect('vacation_form_admin')
    else:
        return redirect('vacation_form_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def vacation_form_admin(request):
    # ----- POST: atender (aprobar / rechazar) -----
    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        accion = request.POST.get('accion')      # 'aprobar' o 'rechazar'
        comentario = request.POST.get('comentario', '').strip()
        pdf_respuesta = request.FILES.get('pdf_respuesta')

        try:
            req = VacationRequest.objects.get(pk=req_id)
        except VacationRequest.DoesNotExist:
            messages.error(request, 'La solicitud indicada no existe.')
            return redirect('vacation_form_admin')
        
        if req.status != 'pending':
            messages.error(request, 'Esta solicitud ya fue atendida y no puede modificarse.')
            return redirect('vacation_form_admin')

        if accion == 'aprobar':
            req.status = 'approved'
            msg = 'aprobada'
        elif accion == 'rechazar':
            req.status = 'rejected'
            msg = 'rechazada'
        else:
            messages.error(request, 'Acción no válida.')
            return redirect('vacation_form_admin')

        # Guardar comprobante en el mismo FileField (documento)
        if pdf_respuesta:
            req.documento = pdf_respuesta

        # Guardar comentario en reason (puedes ajustar si quieres otro campo)
        if comentario:
            if req.reason:
                req.reason = f"{req.reason}\n\nRespuesta: {comentario}"
            else:
                req.reason = comentario

        req.save()
        messages.success(request, f'La solicitud #{req.id} fue {msg}.')
        return redirect('vacation_form_admin')

    # ----- GET: listar con filtros + paginación -----
    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or '').strip()   # pending / approved / rejected
    tipo   = (request.GET.get('tipo') or '').strip()     # Vacaciones, Descanso médico, etc.

    qs = VacationRequest.objects.select_related('user').order_by('-created_at')

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )

    if estado:
        # debe coincidir con los values del <select id="filtro-estado">
        qs = qs.filter(status=estado)

    if tipo:
        # debe coincidir con los values del <select id="filtro-tipo">
        qs = qs.filter(tipo_solicitud=tipo)

    paginator = Paginator(qs, 20)  # 20 por página, ajusta si quieres
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'q': q,
        'estado': estado,
        'tipo': tipo,
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)


# esta vista es para el usuario
@login_required
def vacation_form_user(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_solicitud')          # Vacaciones / Días de estudio / ...
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin    = request.POST.get('fecha_fin')
        observaciones = request.POST.get('observaciones', '').strip()
        documento = request.FILES.get('documento')

        # 1️⃣ Validar que no tenga ya una solicitud pendiente de ese tipo
        ya_pendiente = VacationRequest.objects.filter(
            user=request.user,
            tipo_solicitud=tipo,
            status='pending'
        ).exists()

        if ya_pendiente:
            messages.error(
                request,
                f'Ya tienes una solicitud de "{tipo}" en proceso. '
                'Espera a que sea atendida antes de enviar otra.'
            )
            return redirect('vacation_form_user')

        # 2️⃣ Validar fechas
        try:
            start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            end_date   = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            messages.error(request, 'Las fechas no son válidas.')
            return redirect('vacation_form_user')

        if end_date < start_date:
            messages.error(request, 'La fecha fin no puede ser menor a la fecha inicio.')
            return redirect('vacation_form_user')

        # 3️⃣ No permitir más días de vacaciones de los que tiene
        # (solo aplica cuando es tipo "Vacaciones")
        if tipo == 'Vacaciones':
            dias_solicitados = (end_date - start_date).days + 1  # incluye ambos días
            saldo = float(getattr(request.user.employee, 'vacation_balance', 0) or 0)

            if dias_solicitados > saldo:
                messages.error(
                    request,
                    'No es posible procesar la solicitud porque excede tu saldo de días de vacaciones disponibles.'
                )
                return redirect('vacation_form_user')

        # 4️⃣ Crear registro (status = pending por default en el modelo)
        VacationRequest.objects.create(
            user=request.user,
            tipo_solicitud=tipo,
            start_date=start_date,
            end_date=end_date,
            reason=observaciones,
            documento=documento,
        )

        messages.success(request, 'Tu solicitud se envió correctamente.')
        return redirect('vacation_form_user')

    # GET: listas para las pestañas
    pending_requests = VacationRequest.objects.filter(
        user=request.user,
        status='pending'
    ).order_by('-created_at')

    finished_requests = VacationRequest.objects.filter(
        user=request.user
    ).exclude(status='pending').order_by('-created_at')

    # Si quieres seguir sabiendo cuántos días están en proceso (solo informativo)
    pending_vacations = [
        r for r in pending_requests
        if r.tipo_solicitud == 'Vacaciones'
    ]
    pending_vacation_days = sum(
        (r.end_date - r.start_date).days + 1
        for r in pending_vacations
    )

    # 👇 Este es el saldo tal cual viene de la BD (Tress / proceso nocturno)
    saldo_total = float(getattr(request.user.employee, 'vacation_balance', 0) or 0)

    context = {
        'pending_requests': pending_requests,
        'finished_requests': finished_requests,
        'pending_vacation_days': pending_vacation_days,  # opcional si lo quieres mostrar
        'saldo_total': saldo_total,
    }
    return render(request, 'vacations/user/vacation_form_user.html', context)