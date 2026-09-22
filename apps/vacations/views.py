from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages
from datetime import datetime, date, timedelta
from itertools import groupby
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
from apps.notifications.models import Notification
from django.http import HttpResponse
import csv
import re
import json

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

            # Si el último token es una inicial truncada (1-2 chars),
            # usar el penúltimo token como apellido para no hacer icontains de 1 letra.
            # Ej: "Jonathan Gomez A" → apellido="Gomez", no "A"
            last_token = tokens[-1]
            apellido_token = tokens[-2] if (len(last_token) <= 2 and len(tokens) >= 3) else last_token

            # Intento 1: primer token = first_name, apellido_token en last_name
            qs = Employee.objects.filter(
                first_name__istartswith=tokens[0],
                last_name__icontains=apellido_token,
                **base
            )
            # Intento 2: primer token = last_name, apellido_token en first_name
            if not qs.exists():
                qs = Employee.objects.filter(
                    last_name__istartswith=tokens[0],
                    first_name__icontains=apellido_token,
                    **base
                )
            # Intento 3 (3+ tokens): usar el segundo token como apellido
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


def _normalize(s):
    """Normaliza texto a minúsculas sin espacios dobles."""
    return ' '.join((s or '').split()).lower()


def _employees_of_leader(user):
    """
    Retorna queryset de Employee que tienen a este usuario como líder directo.
    Usa leader_fk (FK directa) para una consulta SQL instantánea.
    """
    try:
        emp_user = Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        return Employee.objects.none()
    return Employee.objects.filter(leader_fk=emp_user, is_active=True)


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
    if request.user.is_staff and request.user.has_perm('vacations.Modulo_vacaciones'):
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

        if tipo in ('Home Office', 'Permiso sin Goce de Sueldo'):
            if len(observaciones) < 20:
                messages.error(request, 'La razón del movimiento debe tener al menos 20 caracteres.')
                return redirect('vacation_form_user')
            if len(observaciones) > 500:
                messages.error(request, 'La razón del movimiento no puede superar los 500 caracteres.')
                return redirect('vacation_form_user')

        if tipo == 'Vacaciones' and len(observaciones) > 1000:
            messages.error(request, 'Las observaciones no pueden superar los 1000 caracteres.')
            return redirect('vacation_form_user')
        documento = request.FILES.get('documento')

        if documento:
            allowed_types = {'application/pdf', 'image/jpeg', 'image/png'}
            allowed_exts  = {'.pdf', '.jpg', '.jpeg', '.png'}
            import os
            ext = os.path.splitext(documento.name)[1].lower()
            if documento.content_type not in allowed_types or ext not in allowed_exts:
                messages.error(request, 'El documento debe ser PDF, JPG o PNG.')
                return redirect('vacation_form_user')
            if documento.size > 10 * 1024 * 1024:  # 10 MB
                messages.error(request, 'El documento no puede superar los 10 MB.')
                return redirect('vacation_form_user')

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

            pasadas = [d.strftime('%d/%m/%Y') for d in fechas if d < date.today()]
            if pasadas:
                messages.error(request, f'No puedes seleccionar fechas pasadas: {", ".join(pasadas)}.')
                return redirect('vacation_form_user')

            fines_semana = [d.strftime('%d/%m/%Y') for d in fechas if d.weekday() >= 5]
            if fines_semana:
                messages.error(request, f'No puedes seleccionar sábados ni domingos: {", ".join(fines_semana)}.')
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

            if tipo == 'Home Office':
                if start_date < date.today():
                    messages.error(request, 'No puedes solicitar Home Office para una fecha pasada.')
                    return redirect('vacation_form_user')
                if start_date.weekday() >= 5:
                    messages.error(request, 'No puedes solicitar Home Office en sábado o domingo.')
                    return redirect('vacation_form_user')

            if tipo == 'Permiso sin Goce de Sueldo':
                if start_date < date.today():
                    messages.error(request, 'No puedes solicitar Permiso sin Goce de Sueldo para una fecha pasada.')
                    return redirect('vacation_form_user')
                if start_date.weekday() >= 5:
                    messages.error(request, 'No puedes solicitar Permiso sin Goce de Sueldo en sábado o domingo.')
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
            nombre_emp = f"{emp_profile.first_name} {emp_profile.last_name}"

            lider_emp = emp_profile.leader_fk

            if lider_emp and lider_emp.user and lider_emp.user.is_active:
                Notification.objects.create(
                    user=lider_emp.user,
                    title="Nueva Solicitud de Vacaciones",
                    body=f"{nombre_emp} ha solicitado {tipo}.",
                    url="/vacations/gestion/",
                    module="vacaciones"
                )
            else:
                motivo = "sin líder asignado" if not emp_profile.leader_fk else "líder sin usuario activo"
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
        user=request.user, status__in=['pending', 'zona_pending']
    ).order_by('-created_at')

    finished_qs = VacationRequest.objects.filter(
        user=request.user
    ).exclude(status__in=['pending', 'zona_pending']).order_by('-created_at')
    finished_page = Paginator(finished_qs, 10).get_page(request.GET.get('page_finished'))

    try:
        emp = Employee.objects.get(user=request.user)
        saldo_total = float(emp.vacation_balance or 0)
        # Resolver a quién fue enviada cada solicitud pendiente
        lider_emp = emp.leader_fk
        if lider_emp:
            enviada_a = f"{lider_emp.first_name} {lider_emp.last_name}"
            puesto_lider = lider_emp.job_position.title if lider_emp.job_position else ""
        elif (emp.leader or '').strip():
            enviada_a = "Capital Humano (líder sin acceso al sistema)"
            puesto_lider = ""
        else:
            enviada_a = "Capital Humano (sin líder asignado)"
            puesto_lider = ""
    except Employee.DoesNotExist:
        saldo_total = 0
        enviada_a = "Capital Humano"
        puesto_lider = ""

    soy_jefe = is_manager(request.user)

    try:
        titulo = request.user.employee.job_position.title if request.user.employee.job_position else ''
        es_jefe_zona = 'jefe de zona' in titulo.lower()
    except Exception:
        es_jefe_zona = False

    context = {
        'pending_requests': pending_requests,
        'finished_page': finished_page,
        'saldo_total': saldo_total,
        'is_manager': soy_jefe,
        'es_jefe_zona': es_jefe_zona,
        'enviada_a': enviada_a,
        'puesto_lider': puesto_lider,
    }
    return render(request, 'vacations/user/vacation_form_user.html', context)


# ==========================================
# 2b. EDITAR SOLICITUD (por el propio usuario, solo pending)
# ==========================================
@login_required
def vacation_edit_user(request, pk):
    if request.method != 'POST':
        return redirect('vacation_form_user')

    req = get_object_or_404(VacationRequest, pk=pk, user=request.user)

    if req.status != 'pending':
        messages.error(request, 'Solo puedes editar solicitudes que aún no han sido autorizadas.')
        return redirect('vacation_form_user')

    tipo = req.tipo_solicitud
    observaciones = request.POST.get('observaciones', '').strip()
    documento = request.FILES.get('documento')

    if tipo in ('Home Office', 'Permiso sin Goce de Sueldo'):
        if len(observaciones) < 20:
            messages.error(request, 'La razón del movimiento debe tener al menos 20 caracteres.')
            return redirect('vacation_form_user')

    if documento:
        import os
        allowed_types = {'application/pdf', 'image/jpeg', 'image/png'}
        allowed_exts  = {'.pdf', '.jpg', '.jpeg', '.png'}
        ext = os.path.splitext(documento.name)[1].lower()
        if documento.content_type not in allowed_types or ext not in allowed_exts:
            messages.error(request, 'El documento debe ser PDF, JPG o PNG.')
            return redirect('vacation_form_user')
        if documento.size > 10 * 1024 * 1024:
            messages.error(request, 'El documento no puede superar los 10 MB.')
            return redirect('vacation_form_user')

    dias_seleccionados_raw = request.POST.get('dias_seleccionados', '').strip()
    fecha_inicio = request.POST.get('fecha_inicio')
    fecha_fin    = request.POST.get('fecha_fin')

    if dias_seleccionados_raw:
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

        pasadas = [d.strftime('%d/%m/%Y') for d in fechas if d < date.today()]
        if pasadas:
            messages.error(request, f'No puedes seleccionar fechas pasadas: {", ".join(pasadas)}.')
            return redirect('vacation_form_user')

        fines = [d.strftime('%d/%m/%Y') for d in fechas if d.weekday() >= 5]
        if fines:
            messages.error(request, f'No puedes seleccionar sábados ni domingos: {", ".join(fines)}.')
            return redirect('vacation_form_user')

        if tipo == 'Vacaciones':
            try:
                emp = Employee.objects.get(user=request.user)
                saldo = float(emp.vacation_balance or 0)
            except Employee.DoesNotExist:
                saldo = 0.0
            if len(fechas) > saldo:
                messages.error(request, 'No tienes saldo suficiente de vacaciones.')
                return redirect('vacation_form_user')

        req.start_date = fechas[0]
        req.end_date   = fechas[-1]
        req.selected_dates = ','.join(d.strftime('%Y-%m-%d') for d in fechas)

    else:
        try:
            start_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            end_date   = datetime.strptime(fecha_fin,    '%Y-%m-%d').date()
        except (TypeError, ValueError):
            messages.error(request, 'Las fechas no son válidas.')
            return redirect('vacation_form_user')

        if end_date < start_date:
            messages.error(request, 'La fecha fin no puede ser menor a la fecha inicio.')
            return redirect('vacation_form_user')

        req.start_date = start_date
        req.end_date   = end_date
        req.selected_dates = None

    req.reason = observaciones
    if documento:
        req.documento = documento
    req.save()

    messages.success(request, 'Solicitud actualizada correctamente.')
    return redirect('vacation_form_user')


# ==========================================
# 2c. CANCELAR SOLICITUD (por el propio usuario)
# ==========================================
@login_required
def vacation_cancel_user(request, pk):
    if request.method != 'POST':
        return redirect('vacation_form_user')

    req = get_object_or_404(VacationRequest, pk=pk, user=request.user)

    if req.status != 'pending':
        messages.error(request, 'Solo puedes cancelar solicitudes que aún no han sido autorizadas.')
        return redirect('vacation_form_user')

    # Eliminar notificación enviada al jefe para esta solicitud
    try:
        emp_profile = Employee.objects.get(user=request.user)
        lider_emp = emp_profile.leader_fk
        if lider_emp and lider_emp.user:
            Notification.objects.filter(
                user=lider_emp.user,
                module='vacaciones',
                url='/vacations/gestion/',
                body__icontains=f"{emp_profile.first_name} {emp_profile.last_name}",
            ).filter(
                body__icontains=req.tipo_solicitud,
            ).delete()
    except Exception:
        pass

    req.delete()
    messages.success(request, 'Solicitud eliminada correctamente.')
    return redirect('vacation_form_user')


# ==========================================
# 3. VISTA DE JEFE (RESPONSABLE)
# ==========================================
@login_required
def vacation_form_manager(request):
    # Calcular subordinados una sola vez y reutilizar en todo el view
    mis_empleados = _employees_of_leader(request.user)

    # Seguridad: gerentes, staff, o jefes de zona con solicitudes asignadas
    if not mis_empleados.exists() and not request.user.is_staff and not _has_zona_pending(request.user):
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
                    Notification.objects.create(
                        user=req.user,
                        title="Solicitud Aprobada",
                        body=f"Tu solicitud de {req.tipo_solicitud} fue aprobada por {nombre_actor}.",
                        url="/vacations/mis-solicitudes/?tab=completados",
                        module="vacaciones"
                    )
                except Exception as e:
                    print(f"Error notificando empleado: {e}")
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
                    # Buscar jefe de zona (líder del gerente) via FK directa
                    zona_emp = None
                    try:
                        emp_mgr = Employee.objects.get(user=request.user)
                        zona_emp = emp_mgr.leader_fk
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
                        try:
                            Notification.objects.create(
                                user=req.user,
                                title="Solicitud Aprobada",
                                body=f"Tu solicitud de {req.tipo_solicitud} fue aprobada por {nombre_actor}.",
                                url="/vacations/mis-solicitudes/?tab=completados",
                                module="vacaciones"
                            )
                        except Exception as e:
                            print(f"Error notificando empleado: {e}")
                        _notificar_rh(req, nombre_actor, nombre_empleado)
                else:
                    # Flujo normal: gerente → RH
                    req.status = 'authorized'
                    req.save()
                    msg = 'autorizada. Se envió a Capital Humano.'
                    try:
                        Notification.objects.create(
                            user=req.user,
                            title="Solicitud Aprobada",
                            body=f"Tu solicitud de {req.tipo_solicitud} fue aprobada por {nombre_actor}.",
                            url="/vacations/mis-solicitudes/?tab=completados",
                            module="vacaciones"
                        )
                    except Exception as e:
                        print(f"Error notificando empleado: {e}")
                    _notificar_rh(req, nombre_actor, nombre_empleado)
        # ------------------------------------------------------------------

        messages.success(request, f'Solicitud #{req.id} {msg}')
        return redirect('vacation_form_manager')

    # --- GET: Listar Historial ---
    estado = request.GET.get('estado', 'activos')
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    qs = VacationRequest.objects.filter(
        Q(user__employee__in=mis_empleados) |
        Q(zona_approver=request.user)
    ).select_related('user', 'user__employee', 'user__employee__department', 'manager_approver', 'manager_approver__employee', 'zona_approver', 'zona_approver__employee').order_by('start_date', 'created_at')

    if estado == 'activos':
        qs = qs.filter(status__in=['pending', 'zona_pending'])
    elif estado and estado != 'todos':
        qs = qs.filter(status=estado)

    if tipo:
        qs = qs.filter(tipo_solicitud=tipo)

    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))

    for r in page_obj.object_list:
        try:
            lider_fk = r.user.employee.leader_fk
            r.lider_name = f"{lider_fk.first_name} {lider_fk.last_name}".strip() if lider_fk else (r.user.employee.leader or '')
        except Exception:
            r.lider_name = ''

        approver_puesto = ''
        try:
            if r.status == 'zona_pending' and r.zona_approver:
                approver_puesto = r.zona_approver.employee.job_position.title or ''
            elif r.status == 'pending':
                lider_fk = r.user.employee.leader_fk
                if lider_fk and lider_fk.job_position:
                    approver_puesto = lider_fk.job_position.title or ''
            elif r.status == 'authorized':
                approver_puesto = 'Capital Humano'
        except Exception:
            pass
        r.approver_puesto = approver_puesto

    week_groups = [
        {'label': label, 'requests': list(grp)}
        for label, grp in groupby(page_obj.object_list, key=lambda r: _semana_label(r.start_date))
    ]

    # Calendario: pendientes del líder y aprobadas/autorizadas (verde desde que el líder aprueba)
    cal_qs = VacationRequest.objects.filter(
        user__employee__in=mis_empleados,
        status__in=['pending', 'authorized', 'approved']
    ).select_related('user', 'user__employee', 'user__employee__leader_fk', 'zona_approver')

    _cal_colors = {
        'pending':    '#6c757d',
        'authorized': '#0d6efd',
        'approved':   '#0d6efd',
    }

    calendar_events = []
    for r in cal_qs:
        nombre = r.user.get_full_name() or r.user.username
        try:
            lider_fk = r.user.employee.leader_fk
            lider_name = f"{lider_fk.first_name} {lider_fk.last_name}".strip() if lider_fk else (r.user.employee.leader or '')
        except Exception:
            lider_name = ''
        zona_name = r.zona_approver.get_full_name() if r.zona_approver else ''
        props = {
            'req_id': r.pk,
            'empleado': nombre,
            'tipo': r.tipo_solicitud,
            'dias': r.total_days or 0,
            'estado': r.status,
            'razon': r.reason or '',
            'comentario_lider': r.comentario_lider or '',
            'comentario_rh': r.comentario_rh or '',
            'documento': r.documento.url if r.documento else '',
            'documento_lider': r.documento_lider.url if r.documento_lider else '',
            'dates_csv': r.selected_dates or '',
            'lider': lider_name,
            'zona_approver': zona_name,
            'inicio': r.dates_display,
        }
        color = _cal_colors.get(r.status, '#6c757d')
        dias_individuales = r.selected_dates_list
        if dias_individuales:
            # Un evento por cada día seleccionado individualmente
            for d in dias_individuales:
                calendar_events.append({
                    'id': f'{r.pk}_{d}',
                    'title': nombre,
                    'start': d.strftime('%Y-%m-%d'),
                    'end': (d + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'color': color,
                    'extendedProps': props,
                })
        else:
            end_exclusive = (r.end_date + timedelta(days=1)).strftime('%Y-%m-%d')
            calendar_events.append({
                'id': r.pk,
                'title': nombre,
                'start': r.start_date.strftime('%Y-%m-%d'),
                'end': end_exclusive,
                'color': color,
                'extendedProps': props,
            })

    context = {
        'page_obj': page_obj,
        'week_groups': week_groups,
        'role': 'manager',
        'q': q,
        'estado': estado,
        'tipo': tipo,
        'calendar_events_json': json.dumps(calendar_events),
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)


# ==========================================
# 4. VISTA DE RH (ADMIN)
# ==========================================
def _semana_label(start_date):
    today = date.today()
    monday_today = today - timedelta(days=today.weekday())
    monday_req = start_date - timedelta(days=start_date.weekday())
    diff = (monday_req - monday_today).days // 7
    if diff < 0:
        return 'Semanas anteriores'
    if diff == 0:
        return 'Esta semana'
    if diff == 1:
        return 'Próxima semana'
    sunday_req = monday_req + timedelta(days=6)
    return f'Semana del {monday_req.strftime("%-d %b")} al {sunday_req.strftime("%-d %b")}'


@user_passes_test(lambda u: u.is_staff and u.has_perm('vacations.Modulo_vacaciones'))
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

        if accion == 'aprobar':
            req.status = 'approved'
            msg = 'registrada y finalizada.'

        elif accion == 'cancelar':
            req.status = 'cancelled'
            if comentario:
                req.comentario_rh = comentario
            req.save()
            try:
                Notification.objects.create(
                    user=req.user,
                    title="Vacaciones Canceladas",
                    body=f"Tu solicitud de {req.tipo_solicitud} ({req.dates_display}) ha sido cancelada por Capital Humano.{' Motivo: ' + comentario if comentario else ''}",
                    url="/vacations/mis-solicitudes/?tab=completados",
                    module="vacaciones"
                )
            except Exception as e:
                print(f"Error enviando notificación de cancelación: {e}")
            messages.success(request, f'Solicitud #{req.id} cancelada.')
            return redirect('vacation_form_rh')

        elif accion == 'rechazar':
            req.status = 'rejected'
            msg = 'rechazada.'
            try:
                Notification.objects.create(
                    user=req.user,
                    title="Solicitud Rechazada",
                    body=f"Tu solicitud de {req.tipo_solicitud} ha sido RECHAZADA por Capital Humano.",
                    url="/vacations/mis-solicitudes/?tab=completados",
                    module="vacaciones"
                )
            except Exception as e:
                print(f"Error enviando notificación al usuario: {e}")

        if pdf: req.documento = pdf
        if comentario: req.comentario_rh = comentario

        req.save()

        messages.success(request, f'Solicitud #{req.id} {msg}')
        return redirect('vacation_form_rh')

    # GET: Listar (RH ve todo, por defecto 'authorized')
    estado = request.GET.get('estado', 'authorized')
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    qs = VacationRequest.objects.select_related('user', 'user__employee', 'user__employee__department', 'manager_approver', 'manager_approver__employee', 'zona_approver', 'zona_approver__employee').order_by('start_date', 'created_at')

    _ESTADO_TIPO_MAP = {
        'authorized_vacaciones': ('authorized', 'Vacaciones'),
        'authorized_permiso':    ('authorized', 'Permiso sin Goce de Sueldo'),
        'authorized_homeoffice': ('authorized', 'Home Office'),
    }

    if estado in _ESTADO_TIPO_MAP:
        _status, _tipo_forzado = _ESTADO_TIPO_MAP[estado]
        qs = qs.filter(status=_status, tipo_solicitud=_tipo_forzado)
    else:
        if estado and estado != 'todos':
            qs = qs.filter(status=estado)
        if tipo:
            qs = qs.filter(tipo_solicitud=tipo)
    if q:
        qs = qs.filter(Q(id__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    week_groups = [
        {'label': label, 'requests': list(grp)}
        for label, grp in groupby(page_obj.object_list, key=lambda r: _semana_label(r.start_date))
    ]

    context = {
        'page_obj': page_obj,
        'week_groups': week_groups,
        'role': 'rh',
        'estado': estado,
        'tipo': tipo,
        'q': q
    }
    return render(request, 'vacations/admin/vacation_form_admin.html', context)


# ==========================================
# 5. EXPORTAR CSV
# ==========================================
@user_passes_test(lambda u: u.is_staff and u.has_perm('vacations.Modulo_vacaciones'))
def vacation_export_csv(request):
    estado = request.GET.get('estado', '')
    tipo   = request.GET.get('tipo', '')
    q      = request.GET.get('q', '').strip()

    qs = VacationRequest.objects.select_related(
        'user', 'user__employee'
    ).order_by('start_date', 'created_at')

    _ESTADO_TIPO_MAP = {
        'authorized_vacaciones': ('authorized', 'Vacaciones'),
        'authorized_permiso':    ('authorized', 'Permiso sin Goce de Sueldo'),
        'authorized_homeoffice': ('authorized', 'Home Office'),
    }

    if estado in _ESTADO_TIPO_MAP:
        _status, _tipo_forzado = _ESTADO_TIPO_MAP[estado]
        qs = qs.filter(status=_status, tipo_solicitud=_tipo_forzado)
    else:
        if estado and estado != 'todos':
            qs = qs.filter(status=estado)
        if tipo:
            qs = qs.filter(tipo_solicitud=tipo)

    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="vacaciones.csv"'
    response.write('\ufeff')  # BOM para que Excel abra correctamente con acentos

    writer = csv.writer(response)
    writer.writerow([
        'Empresa',
        'Num. Empleado',
        'Nombre',
        'Fecha',
        'FechaRegreso',
        'Descrip',
        'DiasPago',
        'DiasPrima',
    ])

    for r in qs:
        try:
            emp = r.user.employee
            empresa       = emp.company or ''
            num_empleado  = emp.employee_number or ''
            nombre        = f"{emp.first_name} {emp.last_name}".strip()
        except Exception:
            empresa      = ''
            num_empleado = ''
            nombre       = r.user.get_full_name() or r.user.username

        fecha_salida  = r.start_date.strftime('%d/%m/%Y') if r.start_date else ''
        fecha_regreso = r.end_date.strftime('%d/%m/%Y') if r.end_date else ''

        writer.writerow([
            empresa,
            num_empleado,
            nombre,
            fecha_salida,
            fecha_regreso,
            r.total_days or '',
            '',   # Días pago (vacío)
            '',   # Días prima (vacío)
        ])

    return response