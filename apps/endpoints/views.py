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


@csrf_exempt
def recibir_datos1(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'mensaje': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body or "{}")

        # ------- Parseo de entrada -------
        nombre_completo = _safe_str(data.get('Nombre'))
        company_name = _safe_str(data.get('Empresa'))

        # Normalización empresa
        if company_name.lower() == 'diaz gas1':
            company_name = 'DIAZ GAS'

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

        # Defaults listos para guardar
        incoming_defaults = {
            "employee_number": employee_number,
            "first_name": first_name,
            "last_name": last_name,
            "department_id": department_id,
            "job_position_id": job_position_id,
            "start_date": start_date,
            "is_active": _as_bool(data.get('Activo')),
            "termination_date": termination_date,
            "rehire_eligible": _as_bool(data.get('Recontratar')),
            "termination_reason": _safe_str(data.get('MotivoBaja')),
            "team": _safe_str(data.get('Equipo')),
            "rfc": _safe_str(data.get('RFC')),
            "imss": _safe_str(data.get('IMSS')),
            "curp": _safe_str(data.get('CURP')),
            "gender": _safe_str(data.get('Genero')),
            "vacation_balance": saldo_vacaciones,
            "phone_number": telefono,
            "address": _safe_str(data.get('Direccion')),

            # Campos por defecto si no vienen del archivo:
            "email": "sin email",
            "birth_date": date(1991, 1, 1),
            "education_level": "sin dato",
            "notes": "Sin observaciones",
            "company": company_name,
        }

        # ------- Crear/Actualizar con diff -------
        with transaction.atomic():
            existing = Employee.objects.select_for_update().filter(employee_number=employee_number).first()

            if not existing:
                # Crear
                empleado = Employee.objects.create(**incoming_defaults)
                # Reportar lo creado (solo campos con valor no vacío/None)
                created_fields = [
                    {'field': k, 'old': None, 'new': v}
                    for k, v in incoming_defaults.items()
                ]
                print(f"[Empleado creado] {empleado.employee_number} -> {empleado.first_name} {empleado.last_name}")
                for ch in created_fields:
                    print(f"  - {ch['field']}: {ch['old']} -> {ch['new']}")
                return JsonResponse({
                    'success': True,
                    'status': 'created',
                    'mensaje': f'Empleado creado: {empleado.first_name} {empleado.last_name}',
                    'changes': created_fields
                })

            # Ya existe: comparar diferencias
            fields_to_check = list(incoming_defaults.keys())
            changes, changed_fields = _diff_instance(existing, incoming_defaults, fields_to_check)

            if not changed_fields:
                # Sin cambios reales
                print(f"[Sin cambios] {existing.employee_number} ({existing.first_name} {existing.last_name})")
                return JsonResponse({
                    'success': True,
                    'status': 'no_change',
                    'mensaje': f'Empleado sin cambios: {existing.first_name} {existing.last_name}',
                    'changes': []
                })

            # Aplicar cambios mínimos necesarios
            for f in changed_fields:
                setattr(existing, f, incoming_defaults[f])
            existing.save(update_fields=changed_fields)

            print(f"[Empleado actualizado] {existing.employee_number} -> {existing.first_name} {existing.last_name}")
            for ch in changes:
                print(f"  - {ch['field']}: {ch['old']} -> {ch['new']}")

            return JsonResponse({
                'success': True,
                'status': 'updated',
                'mensaje': f'Empleado actualizado: {existing.first_name} {existing.last_name}',
                'changes': changes
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
