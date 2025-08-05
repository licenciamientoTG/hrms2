import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.employee.models import Employee, JobPosition
from departments.models import Department
from decimal import Decimal, InvalidOperation


@csrf_exempt
def recibir_datos1(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            nombre_completo = data.get('Nombre', '').strip()

            # Separar por coma: 'Apellidos, Nombres'
            if ',' in nombre_completo:
                last_name, first_name = [p.strip() for p in nombre_completo.split(',', 1)]
            else:
                # Si no hay coma, usar lógica anterior como fallback
                partes = nombre_completo.split()
                if len(partes) == 1:
                    first_name = partes[0]
                    last_name = ''
                elif len(partes) == 2:
                    first_name, last_name = partes
                else:
                    first_name = ' '.join(partes[:-1])
                    last_name = partes[-1]

            #en esta parte es donde estoy mapeando al id del departamento
            department_name = data.get('Departamento', '').strip()
            department = Department.objects.filter(name__iexact=department_name).first()
            department_id = department.id if department else None

            # # Vas a buscar el id del Puesto donde el nomre sea igual a data.get('Puesto')
            puesto_nombre = data.get('Puesto', '').strip()
            puesto = JobPosition.objects.filter(title__iexact=puesto_nombre).first()
            job_position_id = puesto.id if puesto else None

            telefono_crudo = data.get('Telefono', '0')
            telefono = ''.join(c for c in telefono_crudo if c.isdigit())[:10]

            try:
                saldo_raw = str(data.get('SaldoVacaciones', '0')).replace(',', '').strip()
                saldo_vacaciones = Decimal(saldo_raw)
            except (InvalidOperation, TypeError):
                saldo_vacaciones = Decimal('0.0000')
            
            defaults = {
                "employee_number": data.get('Numero', '0'),
                "first_name": first_name,
                "last_name": last_name,
                "department_id": department_id,
                "job_position_id": job_position_id,
                "start_date": data.get('FechaIngreso', '0'),
                "is_active": data.get('Activo', '').lower() in ['sí', 'si', '1', 'true'],
                "termination_date": data.get('FechaBaja', '0'),
                "rehire_eligible": data.get('Recontratar', '').lower() in ['sí', 'si', '1', 'true'],
                "termination_reason": data.get('MotivoBaja', '0'),
                "team": data.get('Equipo', ''),
                "rfc": data.get('RFC', '0'),
                "imss": data.get('IMSS', '0'),
                "curp": data.get('CURP', '0'),
                "gender": data.get('Genero', '0'),
                "vacation_balance": saldo_vacaciones,
                "phone_number": telefono,
                "address": data.get('Direccion', '0'),

                "station_id": 1,
                "email": "sin email",
                "birth_date": "1991-01-01",  
                "education_level": "sin dato",
                "notes": "Sin observaciones"
            }

            empleado, creado = Employee.objects.update_or_create(
                employee_number=data.get('Numero', '0'),
                defaults=defaults
            )

            mensaje = "creado" if creado else "actualizado"
            return JsonResponse({'success': True, 'mensaje': f'Empleado {mensaje}: {empleado.first_name} {empleado.last_name}'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        return JsonResponse({'success': False, 'mensaje': 'Método no permitido'}, status=405)