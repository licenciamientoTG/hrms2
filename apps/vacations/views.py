from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
# Asegúrate de que esta ruta sea correcta en tu proyecto
from apps.notifications.models import Notification  

# ==========================================
# HELPER: Obtener nombre real del Manager
# ==========================================
def get_manager_name(user):
    """
    Intenta obtener el nombre exacto que se usaría en el campo 'responsible'.
    """
    try:
        emp = Employee.objects.get(user=user)
        # Construye "PRUEBA USER"
        return f"{emp.first_name} {emp.last_name}".strip() 
    except Employee.DoesNotExist:
        pass

    full_name = f"{user.first_name} {user.last_name}".strip()
    if full_name:
        return full_name
        
    return user.username

def is_manager(user):
    """ Verifica si el usuario aparece como responsable de alguien """
    name_to_search = get_manager_name(user)
    # print(f"DEBUG: Buscando responsable: '{name_to_search}'")
    return Employee.objects.filter(responsible__iexact=name_to_search).exists()

# ==========================================
# 1. ROUTER (Dashboard)
# ==========================================
@login_required
def vacation_dashboard(request):
    if request.user.is_superuser:
        return redirect('vacation_form_rh')
    
    elif is_manager(request.user):
        nombre_jefe = get_manager_name(request.user)
        tiene_pendientes = VacationRequest.objects.filter(
            status='pending',
            user__employee__responsible__iexact=nombre_jefe
        ).exists()

        if tiene_pendientes:
            return redirect('vacation_form_manager')
        else:
            return redirect('vacation_form_user')
        
    else:
        return redirect('vacation_form_user')


# ==========================================
# 2. VISTA DE USUARIO (SOLICITANTE)
# ==========================================
@login_required
def vacation_form_user(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_solicitud')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin    = request.POST.get('fecha_fin')
        observaciones = request.POST.get('observaciones', '').strip()
        documento = request.FILES.get('documento')

        # Validaciones
        ya_pendiente = VacationRequest.objects.filter(
            user=request.user, tipo_solicitud=tipo, status__in=['pending', 'authorized']
        ).exists()

        if ya_pendiente:
            messages.error(request, f'Ya tienes una solicitud de "{tipo}" en proceso.')
            return redirect('vacation_form_user')

        try:
            start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            end_date   = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            messages.error(request, 'Las fechas no son válidas.')
            return redirect('vacation_form_user')

        if end_date < start_date:
            messages.error(request, 'La fecha fin no puede ser menor a la fecha inicio.')
            return redirect('vacation_form_user')

        if tipo == 'Vacaciones':
            dias_solicitados = (end_date - start_date).days + 1
            try:
                emp = Employee.objects.get(user=request.user)
                saldo = float(emp.vacation_balance or 0)
            except Employee.DoesNotExist:
                saldo = 0.0

            if dias_solicitados > saldo:
                messages.error(request, 'No tienes saldo suficiente de vacaciones.')
                return redirect('vacation_form_user')

        # CREAR REGISTRO (Una sola vez)
        nueva_solicitud = VacationRequest.objects.create(
            user=request.user,
            tipo_solicitud=tipo,
            start_date=start_date,
            end_date=end_date,
            reason=observaciones,
            documento=documento,
        )

        # ---------------------------------------------------------
        # ENVIAR NOTIFICACIÓN AL RESPONSABLE
        # ---------------------------------------------------------
        try:
            emp_profile = Employee.objects.get(user=request.user)
            nombre_responsable = emp_profile.responsible.strip()

            if nombre_responsable:
                responsable_user = None
                # Buscar usuario que coincida con el nombre del responsable
                all_users = User.objects.filter(is_active=True)
                for u in all_users:
                    full_name = f"{u.first_name} {u.last_name}".strip()
                    if full_name.lower() == nombre_responsable.lower() or u.username.lower() == nombre_responsable.lower():
                        responsable_user = u
                        break
                
                if responsable_user:
                    Notification.objects.create(
                        user=responsable_user,
                        title="Nueva Solicitud de Vacaciones",
                        body=f"{request.user.get_full_name()} ha solicitado {tipo}.",
                        url="/vacations/gestion/", 
                        module="vacaciones"
                    )
                    # print(f"DEBUG: Notificación enviada a {responsable_user.username}")
        except Exception as e:
            print(f"Error al enviar notificación: {e}")
        # ---------------------------------------------------------

        messages.success(request, 'Solicitud enviada a tu responsable.')
        return redirect('vacation_form_user')

    # GET
    pending_requests = VacationRequest.objects.filter(
        user=request.user, status__in=['pending', 'authorized']
    ).order_by('-created_at')

    finished_requests = VacationRequest.objects.filter(
        user=request.user
    ).exclude(status__in=['pending', 'authorized']).order_by('-created_at')

    try:
        emp = Employee.objects.get(user=request.user)
        saldo_total = float(emp.vacation_balance or 0)
    except Employee.DoesNotExist:
        saldo_total = 0

    soy_jefe = is_manager(request.user) 

    context = {
        'pending_requests': pending_requests,
        'finished_requests': finished_requests,
        'saldo_total': saldo_total,
        'is_manager': soy_jefe,
    }
    return render(request, 'vacations/user/vacation_form_user.html', context)


# ==========================================
# 3. VISTA DE JEFE (RESPONSABLE)
# ==========================================
@login_required
def vacation_form_manager(request):
    # Seguridad
    if not is_manager(request.user) and not request.user.is_superuser:
        return redirect('vacation_form_user')

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        accion = request.POST.get('accion')
        comentario = request.POST.get('comentario', '').strip()

        req = get_object_or_404(VacationRequest, pk=req_id)

        if req.status != 'pending':
            messages.error(request, 'Esta solicitud ya no está pendiente.')
            return redirect('vacation_form_manager')

        # Variables para la notificación
        notif_titulo = ""
        notif_verbo = ""

        if accion == 'aprobar':
            req.status = 'authorized'
            req.manager_approver = request.user 
            msg = 'autorizada. Se envió a Capital Humano.'
            
            # Datos para la notificación
            notif_titulo = "Solicitud Autorizada por Jefe"
            notif_verbo = "autorizado"

        elif accion == 'rechazar':
            req.status = 'rejected'
            msg = 'rechazada.'
            
            # Datos para la notificación
            notif_titulo = "Solicitud Rechazada por Jefe"
            notif_verbo = "rechazado"
        else:
            return redirect('vacation_form_manager')
        
        if comentario:
            req.reason = f"{req.reason or ''}\n\n[Responsable]: {comentario}"
        
        req.save()

        # ---------------------------------------------------------
        # NOTIFICACIÓN AL ADMINISTRADOR (RH)
        # ---------------------------------------------------------
        try:
            # Buscamos a todos los usuarios administradores (RH)
            rh_users = User.objects.filter(is_superuser=True, is_active=True)

            nombre_jefe = request.user.get_full_name() or request.user.username
            nombre_empleado = req.user.get_full_name() or req.user.username

            for rh in rh_users:
                Notification.objects.create(
                    user=rh,  # Destinatario (Cada admin)
                    title=notif_titulo,
                    body=f"El jefe {nombre_jefe} ha {notif_verbo} la solicitud de {nombre_empleado}.",
                    url="/vacations/capital-humano/", # Link directo a la bandeja de RH
                    module="vacaciones"
                )
            print(f"DEBUG: Notificación enviada a {rh_users.count()} administradores.")

        except Exception as e:
            print(f"Error enviando notificación a RH: {e}")
        # ---------------------------------------------------------

        messages.success(request, f'Solicitud #{req.id} {msg}')
        return redirect('vacation_form_manager')

    # --- GET: Listar Historial ---
    nombre_jefe = get_manager_name(request.user)
    estado = request.GET.get('estado', 'pending')
    q = request.GET.get('q', '').strip()

    qs = VacationRequest.objects.filter(
        user__employee__responsible__iexact=nombre_jefe
    ).select_related('user', 'manager_approver').order_by('-created_at')

    if estado and estado != 'todos':
        qs = qs.filter(status=estado)

    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    context = {
        'page_obj': Paginator(qs, 20).get_page(request.GET.get('page')),
        'role': 'manager',
        'q': q,
        'estado': estado 
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)


# ==========================================
# 4. VISTA DE RH (ADMIN)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_superuser)
def vacation_form_rh(request):
    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        accion = request.POST.get('accion')
        comentario = request.POST.get('comentario', '').strip()
        pdf = request.FILES.get('pdf_respuesta')

        req = get_object_or_404(VacationRequest, pk=req_id)

        # RH trabaja idealmente sobre las autorizadas
        if req.status != 'authorized':
             messages.warning(request, 'Atención: Estás procesando una solicitud que no estaba en estatus de "Autorizada por Jefe".')

        notif_titulo = ""
        notif_cuerpo = ""

        if accion == 'aprobar':
            req.status = 'approved' # ESTADO FINAL
            msg = 'registrada y finalizada.'
            
            # Datos para notificación al usuario
            notif_titulo = "Solicitud Aprobada"
            notif_cuerpo = f"Tu solicitud de {req.tipo_solicitud} ha sido APROBADA y registrada por Capital Humano."

        elif accion == 'rechazar':
            req.status = 'rejected'
            msg = 'rechazada.'
            
            # Datos para notificación al usuario
            notif_titulo = "Solicitud Rechazada"
            notif_cuerpo = f"Tu solicitud de {req.tipo_solicitud} ha sido RECHAZADA por Capital Humano."
        
        if pdf: req.documento = pdf
        if comentario: req.reason = f"{req.reason or ''}\n\n[RH]: {comentario}"

        req.save()

        # ---------------------------------------------------------
        # NOTIFICACIÓN FINAL AL USUARIO (EMPLEADO)
        # ---------------------------------------------------------
        try:
            Notification.objects.create(
                user=req.user,  # El dueño de la solicitud
                title=notif_titulo,
                body=notif_cuerpo,
                url="/vacations/mis-solicitudes/", # Link a su historial
                module="vacaciones"
            )
            print(f"DEBUG: Notificación final enviada al usuario {req.user.username}")
        except Exception as e:
            print(f"Error enviando notificación al usuario: {e}")
        # ---------------------------------------------------------

        messages.success(request, f'Solicitud #{req.id} {msg}')
        return redirect('vacation_form_rh')

    # GET: Listar (RH ve todo, por defecto 'authorized')
    estado = request.GET.get('estado', 'authorized')
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    qs = VacationRequest.objects.select_related('user').order_by('-created_at')

    if estado and estado != 'todos':
        qs = qs.filter(status=estado)
    if tipo:
        qs = qs.filter(tipo_solicitud=tipo)
    if q:
        qs = qs.filter(Q(id__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    context = {
        'page_obj': Paginator(qs, 20).get_page(request.GET.get('page')),
        'role': 'rh',
        'estado': estado,
        'tipo': tipo,
        'q': q
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)