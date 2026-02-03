from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils.timezone import now
from django.db import transaction
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import json

from apps.employee.models import Employee
from departments.models import Department
from apps.employee.models import JobPosition  # ajusta el import a tu estructura real
from django.contrib.auth.models import User


def _as_bool(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ('sí', 'si', 'true', '1', 'y', 'yes')

def _as_decimal(v, default='0'):
    try:
        s = (str(v) if v is not None else str(default)).replace(',', '').strip()
        return Decimal(s or default)
    except (InvalidOperation, TypeError):
        return Decimal(str(default))

def _clean_phone(v):
    digits = ''.join(c for c in str(v or '') if c.isdigit())
    return digits[:10] if digits else ''

def _as_date(v):
    """
    Acepta YYYY-MM-DD o ISO. Devuelve date o None si no hay valor 'real'.
    Evita usar '0'/'0000-00-00' como fecha.
    """
    if not v:
        return None
    s = str(v).strip()
    if s in ('0', '0000-00-00'):
        return None
    # Ya es date
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    # ISO con tiempo
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        pass
    # Solo fecha
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None

def _safe_str(v, default=''):
    s = (v or '').strip() if isinstance(v, str) else (str(v).strip() if v is not None else '')
    return s if s else default

def _diff_instance(current, incoming_dict, field_names):
    """
    Compara valores actuales vs entrantes y devuelve:
    - changes: lista de dicts {field, old, new}
    - changed_fields: lista de nombres a actualizar
    Nota: convierte tipos básicos para comparación segura.
    """
    changes = []
    changed_fields = []

    for f in field_names:
        old = getattr(current, f, None)
        new = incoming_dict.get(f, None)

        # Normalizar para comparar Decimals y fechas
        if isinstance(old, Decimal):
            try:
                new = Decimal(str(new)) if new is not None else None
            except Exception:
                pass
        if isinstance(old, date) and not isinstance(old, datetime):
            if isinstance(new, datetime):
                new = new.date()

        if old != new:
            changes.append({
                'field': f,
                'old': None if old == '' else old,
                'new': None if new == '' else new
            })
            changed_fields.append(f)

    return changes, changed_fields

def _create_user_for_employee(employee):
    """
    Crea usuario para empleado activo. 
    Si el username (reloj) ya está ocupado por OTRA persona, agrega un sufijo (1, 2...).
    """
    if not employee.is_active:
        return None, "Empleado no está activo"
    
    if employee.user:
        return employee.user, "Ya tiene usuario"
    
    try:
        from authapp.models import UserProfile
        
        emp_number = str(employee.employee_number).strip()
        # Contraseña basada en CURP (posiciones 4 a 10)
        birth_date_part = employee.curp[4:10] if employee.curp and len(employee.curp) >= 10 else "000000"
        
        username = emp_number
        password = f"{emp_number}{birth_date_part}"

        # LÓGICA DE SUFIJO: Si el nombre de usuario ya existe
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            # Si el usuario existe, verificamos si es de este mismo empleado (raro por OneToOne pero preventivo)
            existing_user = User.objects.get(username=username)
            if hasattr(existing_user, 'employee') and existing_user.employee == employee:
                break 
            
            # Si es de otra persona, agregamos el sufijo
            username = f"{base_username}{counter}"
            counter += 1

        # Crear usuario de Django
        user = User.objects.create_user(
            username=username,
            email=employee.email or "",
            password=password,
            first_name=employee.first_name,
            last_name=employee.last_name,
            is_active=True
        )

        # Crear perfil de usuario
        UserProfile.objects.create(user=user)
        
        # Vincular al empleado
        employee.user = user
        employee.save(update_fields=['user'])

        return user, f"Usuario creado: {username}"
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def _handle_duplicate_employees(employee_number, start_date, curp=None, rfc=None):
    # 1. Búsqueda por la verdadera identidad: Reloj + CURP
    # Esto hará que Omar (CURP AALO...) e Itze (CURP MOEI...) sean distintos
    match = Employee.objects.filter(
        employee_number=employee_number,
        curp__iexact=_safe_str(curp).strip()
    ).first()

    if match:
        # Si coincide CURP y Reloj, es la misma persona
        return match, "exact_match"
    
    # 2. Si la CURP no coincide, devolvemos None. 
    # Esto obligará a crear un registro NUEVO para Itze.
    return None, "no_existing"

def _apply_seniority(employee, seniority_raw, overwrite=True):
    """Guarda seniority_raw siempre que venga algo.
    Si overwrite=True, sobreescribe aunque ya exista."""
    val = _safe_str(seniority_raw)
    if not val:
        return False
    if overwrite or (employee.seniority_raw or "").strip() != val:
        employee.seniority_raw = val
        employee.save(update_fields=["seniority_raw"])
        return True
    return False

@csrf_exempt
def recibir_datos1(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'mensaje': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body or "{}")

        # ------- Parseo de entrada -------
        nombre_completo = _safe_str(data.get('Nombre'))
        company_name = _safe_str(data.get('Empresa'))

        # Nombre: 'Apellidos, Nombres' -> last_name, first_name
        if ',' in nombre_completo:
            last_name, first_name = [p.strip() for p in nombre_completo.split(',', 1)]
        else:
            partes = nombre_completo.split()
            if len(partes) == 1:
                first_name, last_name = partes[0], ''
            elif len(partes) == 2:
                first_name, last_name = partes
            else:
                first_name = ' '.join(partes[:-1])
                last_name = partes[-1] if partes else ''

        # Department (case-insensitive)
        department_name = _safe_str(data.get('Departamento'))
        department = Department.objects.filter(name__iexact=department_name).first()
        department_id = department.id if department else None

        # JobPosition (case-insensitive)
        puesto_nombre = _safe_str(data.get('Puesto'))
        puesto = JobPosition.objects.filter(title__iexact=puesto_nombre).first()
        job_position_id = puesto.id if puesto else None

        telefono = _clean_phone(data.get('Telefono'))
        saldo_vacaciones = _as_decimal(data.get('SaldoVacaciones'), '0')

        start_date = _as_date(data.get('FechaIngreso'))
        termination_date = _as_date(data.get('FechaBaja'))

        employee_number = _safe_str(data.get('Numero'), '0')
        incoming_is_active = _as_bool(data.get('Activo'))

        seniority_raw = _safe_str(data.get('Antiguedad'))

        email = _safe_str(data.get('Correo'))

        fondo_ahorro = _as_decimal(data.get('FondoAhorro'), '0')
        salario_diario = _as_decimal(data.get('SalarioDiario'), '0')
        responsable = _safe_str(data.get('Responsable'))

        grat_separacion = _as_decimal(data.get('Grat.Separacion'), '0')
        indemnizacion = _as_decimal(data.get('Indemnizacion'), '0')
        prima_antig = _as_decimal(data.get('PrimaDeAntig.'), '0')

        # ------- Limpieza de datos antes de guardar (Prevenir Error 400) -------
        # 1. Sexo: Convertir 'Masculino' -> 'M', 'Femenino' -> 'F'
        genero_raw = _safe_str(data.get('Genero', '')).upper()
        if 'MAS' in genero_raw or genero_raw == 'H' or genero_raw == 'M':
            gender = 'M'
        elif 'FEM' in genero_raw or genero_raw == 'F' or genero_raw == 'W':
            gender = 'F'
        else:
            gender = 'M' # Default seguro

        # 2. Teléfono: Asegurar 10 dígitos o vaciarlo para que no truene el RegexValidator
        telefono = _clean_phone(data.get('Telefono'))
        if len(telefono) != 10:
            telefono = '0000000000' # Valor placeholder válido para el regex

        # 3. Fechas: Manejar el 1900-01-01 de Tress como None
        start_date = _as_date(data.get('FechaIngreso'))
        termination_date = _as_date(data.get('FechaBaja'))
        if termination_date and termination_date.year <= 1901:
            termination_date = None

        incoming_is_active = _as_bool(data.get('Activo'))

        # ------- Limpieza de datos antes de guardar (Prevenir Error 400) -------
        # 1. Sexo: El modelo espera 'M' o 'F'
        genero_raw = _safe_str(data.get('Genero', '')).upper()
        if 'MAS' in genero_raw or genero_raw == 'H' or genero_raw == 'M':
            gender = 'M'
        elif 'FEM' in genero_raw or genero_raw == 'F' or genero_raw == 'W':
            gender = 'F'
        else:
            gender = 'M'

        # 2. Teléfono: Asegurar 10 dígitos para el validador
        telefono = _clean_phone(data.get('Telefono'))
        if len(telefono) != 10:
            telefono = '0000000000'

        # 3. Fechas
        start_date = _as_date(data.get('FechaIngreso'))
        termination_date = _as_date(data.get('FechaBaja'))
        if termination_date and termination_date.year <= 1901:
            termination_date = None

        incoming_is_active = _as_bool(data.get('Activo'))

        # Defaults para el registro
        incoming_defaults = {
            "employee_number": employee_number,
            "first_name": first_name,
            "last_name": last_name,
            "department_id": department_id,
            "job_position_id": job_position_id,
            "start_date": start_date,
            "is_active": incoming_is_active,
            "termination_date": termination_date,
            "rehire_eligible": _as_bool(data.get('Recontratar')),
            "termination_reason": _safe_str(data.get('MotivoBaja')),
            "team": _safe_str(data.get('Equipo')),
            "rfc": _safe_str(data.get('RFC')),
            "imss": _safe_str(data.get('IMSS')),
            "curp": _safe_str(data.get('CURP')),
            "gender": gender,
            "vacation_balance": saldo_vacaciones,
            "phone_number": telefono,
            "address": _safe_str(data.get('Direccion')),
            "seniority_raw": seniority_raw,
            "company": company_name,
            "education_level": _safe_str(data.get("Estudios", "sin dato")),
            "email": email if email else "",
            "birth_date": date(1991, 1, 1),
            "notes": "Sincronizado con Tress",
            "saving_fund": fondo_ahorro,
            "daily_salary": salario_diario,
            "responsible": responsable,
            "separation_gratuity": grat_separacion,
            "indemnification": indemnizacion,
            "seniority_bonus": prima_antig, 
        }

        # ------- Manejar duplicados con prioridad -------
        with transaction.atomic():
            existing, action = _handle_duplicate_employees(
                employee_number, 
                start_date,
                curp=incoming_defaults.get('curp'),
                rfc=incoming_defaults.get('rfc')
            )

            # 1) No existe -> crear
            if action == "no_existing":
                try:
                    empleado = Employee.objects.create(**incoming_defaults)
                    _apply_seniority(empleado, seniority_raw, overwrite=True)
                    user_message = ""
                    if empleado.is_active:
                        user, user_msg = _create_user_for_employee(empleado)
                        user_message = user_msg
                    return JsonResponse({'success': True, 'status': 'created', 'mensaje': f'Creado: {empleado.first_name}', 'user_info': user_message})
                except Exception as e:
                    return JsonResponse({'success': False, 'error': f"Error al crear: {str(e)}"}, status=400)

            # 2) Actualizar existente
            existing = Employee.objects.select_for_update().filter(id=existing.id).first()
            
            # --- LÓGICA DE ESCUDO ACTIVO ---
            # Si el registro ya está ACTIVO y fue actualizado HOY, ignoramos si este nuevo registro dice "Inactivo"
            # Esto evita que filas viejas de Tress desactiven a alguien que ya vimos que está activo.
            if existing.is_active:
                # Y el dato que llega es INACTIVO (es decir, incoming_is_active != True)
                if not incoming_is_active:
                    # REGLA: Si hoy ya se marcó como activo, ignoramos cualquier dato inactivo
                    today = now().date()
                    if existing.updated_at.date() == today:
                        print(f"🛡️ Ignorando fila de inactivo para {existing.first_name}: Ya está activo hoy.")
                        return JsonResponse({
                            'success': True, 
                            'status': 'protected', 
                            'mensaje': f'{existing.first_name} se mantiene Activo (fila obsoleta ignorada)'
                        })

            fields_to_check = list(incoming_defaults.keys())
            changes, changed_fields = _diff_instance(existing, incoming_defaults, fields_to_check)

            if not changed_fields:
                _apply_seniority(existing, seniority_raw, overwrite=True)
                # Si es activo pero perdió el usuario por error previo, recrearlo
                if existing.is_active and not existing.user:
                    _create_user_for_employee(existing)
                return JsonResponse({'success': True, 'status': 'no_change', 'mensaje': f'Sin cambios: {existing.first_name}'})

            # Aplicar cambios
            for f in changed_fields:
                setattr(existing, f, incoming_defaults[f])
            existing.save(update_fields=changed_fields)
            _apply_seniority(existing, seniority_raw, overwrite=True)

            # Manejar usuario
            user_message = ""
            if existing.is_active:
                if not existing.user:
                    # Intentar liberar el username si lo tiene un zombie
                    try:
                        uname = str(existing.employee_number).strip()
                        zombie = User.objects.filter(username=uname).first()
                        if zombie and not (zombie.is_staff or zombie.is_superuser):
                            if not hasattr(zombie, 'employee') or not zombie.employee.is_active:
                                zombie.delete()
                    except: pass
                    user, user_msg = _create_user_for_employee(existing)
                    user_message = user_msg
                else:
                    # Si ya tiene usuario, asegurarnos que esté activo y sincronizar datos
                    u = existing.user
                    if not u.is_active:
                        u.is_active = True
                        u.save(update_fields=['is_active'])
                    
                    # Sincronizar datos básicos del usuario con el empleado
                    user_changed = False
                    if u.first_name != existing.first_name:
                        u.first_name = existing.first_name
                        user_changed = True
                    if u.last_name != existing.last_name:
                        u.last_name = existing.last_name
                        user_changed = True
                    if u.email != existing.email:
                        u.email = existing.email
                        user_changed = True
                    
                    if user_changed:
                        u.save(update_fields=['first_name', 'last_name', 'email'])
                        user_message = "Usuario actualizado con datos del empleado."
            else:
                # Desactivación real: Si ya no es activo, borramos usuario
                if existing.user:
                    u_borrar = existing.user
                    existing.user = None
                    existing.save(update_fields=['user'])
                    u_borrar.delete()
                    user_message = "Usuario eliminado por inactividad."

            return JsonResponse({
                'success': True,
                'status': 'updated',
                'mensaje': f'Actualizado: {existing.first_name}',
                'changes': changes,
                'user_info': user_message
            })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"🚨 EXCEPCIÓN CRÍTICA en recibir_datos1: {str(e)}\n{error_details}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)