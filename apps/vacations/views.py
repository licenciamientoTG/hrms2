from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
from apps.notifications.models import Notification
import re

# ==========================================
# HELPERS: Lógica de líder (campo leader)
# ==========================================

def _extract_leader_name(leader_raw):
    """
    Quita el prefijo de código/estación del campo leader y retorna solo el nombre.
    Maneja formatos como:
      '1149 - Montes Guillermo, Jose'  -> 'Montes Guillermo, Jose'
      'ADMONFIN - Luis Miguel Franco'  -> 'Luis Miguel Franco'
      '1376-Joel Briseño'              -> 'Joel Briseño'
      'Luis Ivan Meraz Reyes'          -> 'Luis Ivan Meraz Reyes'
    """
    if not leader_raw:
        return ''
    cleaned = re.sub(r'^[\w]+\s*-\s*', '', leader_raw.strip())
    if cleaned.lower() in ('no aplica', 'desconocido', ''):
        return ''
    return cleaned.strip()


def _find_leader_employee(leader_raw):
    """
    A partir del valor crudo del campo leader, encuentra el Employee con usuario
    que corresponde a ese líder. Maneja nombres truncados y ambos formatos
    (con coma 'Apellidos, Nombres' y sin coma 'Nombres Apellidos').
    Retorna None si no lo encuentra.
    """
    name = _extract_leader_name(leader_raw)
    if not name:
        return None

    if ',' in name:
        # Formato "Apellidos, Nombres" — posiblemente truncado
        left, right = name.split(',', 1)
        apellidos = left.strip()
        nombres = right.strip()
        qs = Employee.objects.filter(
            last_name__istartswith=apellidos,
            user__isnull=False,
            user__is_active=True
        )
        if nombres:
            qs = qs.filter(first_name__istartswith=nombres)
    else:
        tokens = name.split()
        if len(tokens) >= 2:
            base = dict(user__isnull=False, user__is_active=True)
            # Intento 1: primer token = first_name, último token en last_name
            qs = Employee.objects.filter(
                first_name__istartswith=tokens[0],
                last_name__icontains=tokens[-1],
                **base
            )
            # Intento 2: primer token = last_name, último token en first_name
            if not qs.exists():
                qs = Employee.objects.filter(
                    last_name__istartswith=tokens[0],
                    first_name__icontains=tokens[-1],
                    **base
                )
            # Intento 3 (3+ tokens): el último puede estar truncado,
            # usar el token del medio como apellido
            if not qs.exists() and len(tokens) >= 3:
                qs = Employee.objects.filter(
                    first_name__istartswith=tokens[0],
                    last_name__icontains=tokens[1],
                    **base
                )
            # Intento 4: primer token = last_name, segundo token en first_name
            if not qs.exists() and len(tokens) >= 3:
                qs = Employee.objects.filter(
                    last_name__istartswith=tokens[0],
                    first_name__icontains=tokens[1],
                    **base
                )
        else:
            qs = Employee.objects.filter(
                Q(first_name__istartswith=name) | Q(last_name__istartswith=name),
                user__isnull=False,
                user__is_active=True
            )

    return qs.select_related('user').first()


def _employees_of_leader(user):
    """
    Retorna queryset de Employee cuyos registros apuntan a este usuario
    en el campo leader, usando búsqueda flexible por nombre (maneja
    los distintos formatos y truncados del campo).
    """
    try:
        emp = Employee.objects.get(user=user)
        last = emp.last_name.strip()
        first = emp.first_name.strip()
    except Employee.DoesNotExist:
        return Employee.objects.none()

    if not last and not first:
        return Employee.objects.none()

    # Usar solo el primer token del apellido y primeros chars del nombre
    # para tolerar truncados en el campo leader (el sistema origen corta el texto)
    last_prefix = last.split()[0][:7] if last else ''
    first_prefix = first[:4] if first else ''

    q = Q()
    if last_prefix:
        q &= Q(leader__icontains=last_prefix)
    if first_prefix:
        q &= Q(leader__icontains=first_prefix)

    return Employee.objects.filter(q)


def get_manager_name(user):
    """Retorna el nombre para mostrar del usuario (usado en notificaciones)."""
    try:
        emp = Employee.objects.get(user=user)
        return f"{emp.first_name} {emp.last_name}".strip()
    except Employee.DoesNotExist:
        return user.get_full_name() or user.username


def is_manager(user):
    """Verifica si el usuario es líder de algún empleado."""
    return _employees_of_leader(user).exists()


def _needs_zona_approval(emp):
    """Retorna True si el puesto del empleado es Oficial de Servicio al Cliente."""
    if not emp.job_position:
        return False
    return 'oficial de servicio al cliente' in (emp.job_position.title or '').lower()


def _has_zona_pending(user):
    """Retorna True si hay solicitudes zona_pending asignadas a este usuario como jefe de zona."""
    return VacationRequest.objects.filter(status='zona_pending', zona_approver=user).exists()


def _notificar_rh(req, nombre_actor, nombre_empleado):
    """Envía notificación a usuarios de RH cuando una solicitud llega a 'authorized'."""
    rh_users = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) |
        Q(is_staff=True, user_permissions__codename='Modulo_vacaciones') |
        Q(is_staff=True, groups__permissions__codename='Modulo_vacaciones')
    ).distinct()
    for rh in rh_users:
        Notification.objects.create(
            user=rh,
            title="Solicitud Autorizada por Jefe",
            body=f"{nombre_actor} autorizó la solicitud de {nombre_empleado}.",
            url="/vacations/capital-humano/",
            module="vacaciones"
        )

# ==========================================
# 1. ROUTER (Dashboard)
# ==========================================
@login_required
def vacation_dashboard(request):
    if request.user.is_staff:
        return redirect('vacation_form_rh')

    tiene_pendientes = is_manager(request.user) and VacationRequest.objects.filter(
        status='pending',
        user__employee__in=_employees_of_leader(request.user)
    ).exists()
    tiene_zona = _has_zona_pending(request.user)

    if tiene_pendientes or tiene_zona:
        return redirect('vacation_form_manager')

    return redirect('vacation_form_user')


# ==========================================
# 2. VISTA DE USUARIO (SOLICITANTE)
# ==========================================
@login_required
def vacation_form_user(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_solicitud')
        observaciones = request.POST.get('observaciones', '').strip()
        documento = request.FILES.get('documento')

        # Soporte para días individuales (modal Vacaciones) y rango clásico (otros modales)
        dias_seleccionados_raw = request.POST.get('dias_seleccionados', '').strip()
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin    = request.POST.get('fecha_fin')

        selected_dates_csv = None

        if dias_seleccionados_raw:
            # Parsear lista de fechas individuales
            try:
                fechas = sorted([
                    datetime.strptime(d.strip(), '%Y-%m-%d').date()
                    for d in dias_seleccionados_raw.split(',') if d.strip()
                ])
            except ValueError:
                messages.error(request, 'Las fechas seleccionadas no son válidas.')
                return redirect('vacation_form_user')

            if not fechas:
                messages.error(request, 'Debes seleccionar al menos un día.')
                return redirect('vacation_form_user')

            start_date = fechas[0]
            end_date   = fechas[-1]
            selected_dates_csv = ','.join(d.strftime('%Y-%m-%d') for d in fechas)
            dias_solicitados = len(fechas)
        else:
            # Flujo clásico (rango) para otros tipos de solicitud
            try:
                start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                end_date   = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                messages.error(request, 'Las fechas no son válidas.')
                return redirect('vacation_form_user')

            if end_date < start_date:
                messages.error(request, 'La fecha fin no puede ser menor a la fecha inicio.')
                return redirect('vacation_form_user')

            dias_solicitados = (end_date - start_date).days + 1

        # Validaciones
        ya_pendiente = VacationRequest.objects.filter(
            user=request.user, tipo_solicitud=tipo, status__in=['pending', 'zona_pending', 'authorized']
        ).exists()

        if ya_pendiente:
            messages.error(request, f'Ya tienes una solicitud de "{tipo}" en proceso.')
            return redirect('vacation_form_user')

        # Validar que no se traslapen con solicitudes ya activas
        solicitudes_activas = VacationRequest.objects.filter(
            user=request.user,
            status__in=['pending', 'zona_pending', 'authorized', 'approved'],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        traslape = None
        nuevos_dias = set(fechas) if dias_seleccionados_raw else None

        for sol in solicitudes_activas:
            dias_existentes = sol.selected_dates_list
            if nuevos_dias and dias_existentes:
                # Comparación exacta por días individuales
                if nuevos_dias & set(dias_existentes):
                    traslape = sol
                    break
            elif nuevos_dias and not dias_existentes:
                # Existente es rango clásico: ver si algún día nuevo cae en ese rango
                if any(sol.start_date <= d <= sol.end_date for d in nuevos_dias):
                    traslape = sol
                    break
            else:
                # Ambos son rango: traslape por rango
                traslape = sol
                break

        if traslape:
            messages.error(
                request,
                f'Ya tienes una solicitud ({traslape.tipo_solicitud}) '
                f'({traslape.dates_display}) que se traslapa con los días seleccionados.'
            )
            return redirect('vacation_form_user')

        if tipo == 'Vacaciones':
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
            selected_dates=selected_dates_csv,
            reason=observaciones,
            documento=documento,
        )

        # ---------------------------------------------------------
        # ENVIAR NOTIFICACIÓN AL LÍDER (con fallback a RH)
        # ---------------------------------------------------------
        try:
            emp_profile = Employee.objects.get(user=request.user)
            leader_raw = (emp_profile.leader or '').strip()
            nombre_emp = f"{emp_profile.first_name} {emp_profile.last_name}"

            lider_emp = _find_leader_employee(leader_raw) if leader_raw else None

            if lider_emp:
                Notification.objects.create(
                    user=lider_emp.user,
                    title="Nueva Solicitud de Vacaciones",
                    body=f"{nombre_emp} ha solicitado {tipo}.",
                    url="/vacations/gestion/",
                    module="vacaciones"
                )
            else:
                # Sin líder, líder sin cuenta o líder inactivo → saltar al flujo de RH
                motivo = "sin líder asignado" if not leader_raw else f"líder '{leader_raw}' no encontrado o inactivo"
                print(f"[Vacaciones] Fallback a RH para {nombre_emp}: {motivo}")

                # Marcar como autorizada para que RH la vea en su bandeja normal
                nueva_solicitud.status = 'authorized'
                nueva_solicitud.save()

                rh_users = User.objects.filter(is_active=True).filter(
                    Q(is_superuser=True) |
                    Q(is_staff=True, user_permissions__codename='Modulo_vacaciones') |
                    Q(is_staff=True, groups__permissions__codename='Modulo_vacaciones')
                ).distinct()
                for rh in rh_users:
                    Notification.objects.create(
                        user=rh,
                        title="Nueva Solicitud de Vacaciones (sin líder)",
                        body=f"{nombre_emp} ha solicitado {tipo}. No tiene líder activo asignado, revisar directamente.",
                        url="/vacations/capital-humano/",
                        module="vacaciones"
                    )
        except Exception as e:
            print(f"Error al enviar notificación: {e}")
        # ---------------------------------------------------------

        messages.success(request, 'Solicitud enviada correctamente.')
        return redirect('vacation_form_user')

    # GET
    pending_requests = VacationRequest.objects.filter(
        user=request.user, status__in=['pending', 'zona_pending', 'authorized']
    ).order_by('-created_at')

    finished_requests = VacationRequest.objects.filter(
        user=request.user
    ).exclude(status__in=['pending', 'authorized']).order_by('-created_at')

    try:
        emp = Employee.objects.get(user=request.user)
        saldo_total = float(emp.vacation_balance or 0)
        # Resolver a quién fue enviada cada solicitud pendiente
        leader_raw = (emp.leader or '').strip()
        lider_emp = _find_leader_employee(leader_raw) if leader_raw else None
        if lider_emp:
            enviada_a = f"{lider_emp.first_name} {lider_emp.last_name}"
        elif leader_raw:
            # Tiene líder en el campo pero no tiene usuario activo
            enviada_a = f"Capital Humano (líder sin acceso al sistema)"
        else:
            enviada_a = "Capital Humano (sin líder asignado)"
    except Employee.DoesNotExist:
        saldo_total = 0
        enviada_a = "Capital Humano"

    soy_jefe = is_manager(request.user)

    context = {
        'pending_requests': pending_requests,
        'finished_requests': finished_requests,
        'saldo_total': saldo_total,
        'is_manager': soy_jefe,
        'enviada_a': enviada_a,
    }
    return render(request, 'vacations/user/vacation_form_user.html', context)


# ==========================================
# 3. VISTA DE JEFE (RESPONSABLE)
# ==========================================
@login_required
def vacation_form_manager(request):
    # Seguridad: gerentes, staff, o jefes de zona con solicitudes asignadas
    if not is_manager(request.user) and not request.user.is_staff and not _has_zona_pending(request.user):
        return redirect('vacation_form_user')

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        accion = request.POST.get('accion')
        comentario = request.POST.get('comentario', '').strip()
        pdf_lider = request.FILES.get('pdf_respuesta')

        req = get_object_or_404(VacationRequest, pk=req_id)

        if req.status not in ('pending', 'zona_pending'):
            messages.error(request, 'Esta solicitud ya no está pendiente.')
            return redirect('vacation_form_manager')

        if accion not in ('aprobar', 'rechazar'):
            return redirect('vacation_form_manager')

        # Solo el jefe de zona asignado puede actuar sobre solicitudes zona_pending
        if req.status == 'zona_pending' and req.zona_approver != request.user:
            messages.error(request, 'No tienes permiso para actuar sobre esta solicitud.')
            return redirect('vacation_form_manager')

        if comentario:
            req.comentario_lider = comentario
        if pdf_lider:
            req.documento_lider = pdf_lider

        nombre_actor = get_manager_name(request.user)
        nombre_empleado = req.user.get_full_name() or req.user.username

        # ------------------------------------------------------------------
        # LÓGICA DE FLUJO
        # ------------------------------------------------------------------
        if accion == 'rechazar':
            req.status = 'rejected'
            req.save()
            msg = 'rechazada.'
            try:
                Notification.objects.create(
                    user=req.user,
                    title="Solicitud Rechazada",
                    body=f"Tu solicitud de {req.tipo_solicitud} fue rechazada por {nombre_actor}.",
                    url="/vacations/mis-solicitudes/?tab=completados",
                    module="vacaciones"
                )
            except Exception as e:
                print(f"Error enviando notificación: {e}")

        elif accion == 'aprobar':
            if req.status == 'zona_pending':
                # Jefe de Zona aprueba → va a RH
                req.status = 'authorized'
                req.save()
                msg = 'autorizada por Jefe de Zona. Se envió a Capital Humano.'
                try:
                    rh_users = User.objects.filter(is_active=True).filter(
                        Q(is_superuser=True) |
                        Q(is_staff=True, user_permissions__codename='Modulo_vacaciones') |
                        Q(is_staff=True, groups__permissions__codename='Modulo_vacaciones')
                    ).distinct()
                    for rh in rh_users:
                        Notification.objects.create(
                            user=rh,
                            title="Solicitud Autorizada por Jefe de Zona",
                            body=f"{nombre_actor} (Jefe de Zona) autorizó la solicitud de {nombre_empleado}.",
                            url="/vacations/capital-humano/",
                            module="vacaciones"
                        )
                except Exception as e:
                    print(f"Error enviando notificación a RH: {e}")

            else:
                # Gerente aprueba (pending) — verificar si el OSC necesita paso por jefe de zona
                req.manager_approver = request.user
                try:
                    emp_sol = Employee.objects.get(user=req.user)
                    necesita_zona = _needs_zona_approval(emp_sol)
                except Employee.DoesNotExist:
                    necesita_zona = False

                if necesita_zona:
                    # Buscar jefe de zona (líder del gerente)
                    zona_emp = None
                    try:
                        emp_mgr = Employee.objects.get(user=request.user)
                        zona_raw = (emp_mgr.leader or '').strip()
                        zona_emp = _find_leader_employee(zona_raw) if zona_raw else None
                    except Employee.DoesNotExist:
                        pass

                    if zona_emp:
                        req.status = 'zona_pending'
                        req.zona_approver = zona_emp.user
                        req.save()
                        msg = 'enviada al Jefe de Zona para su autorización.'
                        try:
                            Notification.objects.create(
                                user=zona_emp.user,
                                title="Solicitud Pendiente de Autorización (Jefe de Zona)",
                                body=f"{nombre_empleado} tiene una solicitud de {req.tipo_solicitud} autorizada por su gerente. Requiere tu autorización.",
                                url="/vacations/gestion/",
                                module="vacaciones"
                            )
                        except Exception as e:
                            print(f"Error notificando jefe de zona: {e}")
                    else:
                        # No se encontró jefe de zona → ir directo a RH
                        req.status = 'authorized'
                        req.save()
                        msg = 'autorizada. Se envió a Capital Humano (jefe de zona no encontrado).'
                        print(f"[Vacaciones] OSC sin jefe de zona para gerente {request.user.username}, enviando directo a RH.")
                        _notificar_rh(req, nombre_actor, nombre_empleado)
                else:
                    # Flujo normal: gerente → RH
                    req.status = 'authorized'
                    req.save()
                    msg = 'autorizada. Se envió a Capital Humano.'
                    _notificar_rh(req, nombre_actor, nombre_empleado)
        # ------------------------------------------------------------------

        messages.success(request, f'Solicitud #{req.id} {msg}')
        return redirect('vacation_form_manager')

    # --- GET: Listar Historial ---
    estado = request.GET.get('estado', 'activos')
    q = request.GET.get('q', '').strip()

    qs = VacationRequest.objects.filter(
        Q(user__employee__in=_employees_of_leader(request.user)) |
        Q(zona_approver=request.user)
    ).select_related('user', 'manager_approver', 'zona_approver').order_by('-created_at')

    if estado == 'activos':
        qs = qs.filter(status__in=['pending', 'zona_pending'])
    elif estado and estado != 'todos':
        qs = qs.filter(status=estado)

    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    context = {
        'page_obj': Paginator(qs, 20).get_page(request.GET.get('page')),
        'role': 'manager',
        'q': q,
        'estado': estado,
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)


# ==========================================
# 4. VISTA DE RH (ADMIN)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_staff)
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
        if comentario: req.comentario_rh = comentario

        req.save()

        # ---------------------------------------------------------
        # NOTIFICACIÓN FINAL AL USUARIO (EMPLEADO)
        # ---------------------------------------------------------
        try:
            Notification.objects.create(
                user=req.user,
                title=notif_titulo,
                body=notif_cuerpo,
                url="/vacations/mis-solicitudes/?tab=completados",
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