import zipfile
import xml.etree.ElementTree as ET
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.employee.models import Employee
from apps.performance.models import PerformanceReviewCycle, PerformanceReview, PerformanceReviewAnswer
from django.db.models import Q
from django.utils import timezone
import json
from django.core.paginator import Paginator
from django.db.models import Count, Avg

class NativeXLSXReader:
    def __init__(self, file_obj):
        self.zip_ref = zipfile.ZipFile(file_obj)
        self.shared_strings = self._parse_shared_strings()
        
    def _parse_shared_strings(self):
        strings = []
        try:
            with self.zip_ref.open('xl/sharedStrings.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for si in root:
                    text_nodes = si.findall(".//{*}t")
                    text_val = "".join([t.text for t in text_nodes if t.text])
                    strings.append(text_val)
        except KeyError:
            pass
        return strings

    def get_sheet_data(self, sheet_name_match="Empleados"):
        # 1. Encontrar el archivo de la hoja
        sheet_filename = None
        try:
            with self.zip_ref.open('xl/workbook.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                r_id = None
                for sheet in root.findall(".//{*}sheet"):
                    name = sheet.attrib.get('name', '')
                    if sheet_name_match.lower() in name.lower():
                        r_id = sheet.attrib.get('r:id') or sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                        break
                
                if r_id:
                    with self.zip_ref.open('xl/_rels/workbook.xml.rels') as f_rels:
                        tree_rels = ET.parse(f_rels)
                        for rel in tree_rels.getroot():
                            if rel.attrib.get('Id') == r_id:
                                target = rel.attrib.get('Target')
                                if target.startswith('/'): target = target[1:]
                                if not target.startswith('xl/'): target = f"xl/{target}"
                                sheet_filename = target
                                break
        except Exception:
            pass

        if not sheet_filename:
            sheet_filename = "xl/worksheets/sheet1.xml"

        # 2. Leer la data (IGNORANDO FILAS OCULTAS)
        raw_rows = {}
        
        try:
            with self.zip_ref.open(sheet_filename) as f:
                tree = ET.parse(f)
                root = tree.getroot()
                sheet_data = root.find("{*}sheetData")
                if sheet_data is None: sheet_data = root.find("sheetData")
                if sheet_data is None: return []

                for row in sheet_data:
                    # --- NUEVO: Detectar si la fila está oculta (filtro de Excel) ---
                    # Excel marca las filas ocultas con hidden="1"
                    is_hidden = row.attrib.get('hidden')
                    if is_hidden == '1' or is_hidden == 'true':
                        continue  # <--- ESTO ES LO QUE ARREGLA TU PROBLEMA
                    
                    r_idx = int(row.attrib.get('r'))
                    row_dict = {}
                    
                    for cell in row:
                        cell_ref = cell.attrib.get('r')
                        cell_type = cell.attrib.get('t')
                        
                        val_tag = cell.find("{*}v")
                        val = ""
                        if val_tag is not None:
                            val = val_tag.text
                            if cell_type == 's': 
                                try: val = self.shared_strings[int(val)]
                                except: pass
                        else:
                            is_tag = cell.find("{*}is/{*}t")
                            if is_tag is not None: val = is_tag.text

                        col_letter = "".join(filter(str.isalpha, cell_ref))
                        row_dict[col_letter] = val
                    
                    if row_dict:
                        raw_rows[r_idx] = row_dict

        except KeyError:
            return []

        # 3. Encontrar encabezados (Buscando "Número")
        header_row_idx = None
        headers_map = {}

        sorted_rows = sorted(raw_rows.keys())
        # Buscamos en las primeras 20 filas visibles
        for r in sorted_rows[:20]: 
            row_values = raw_rows[r]
            found_header = False
            for col, val in row_values.items():
                if val and 'número' in str(val).lower():
                    found_header = True
                    break
            
            if found_header:
                header_row_idx = r
                for col, val in row_values.items():
                    headers_map[col] = str(val).lower().strip()
                break
        
        if not header_row_idx:
            return []

        # 4. Construir lista final
        final_data = []
        for r in sorted_rows:
            if r <= header_row_idx: continue
            
            processed_row = {}
            raw_row_data = raw_rows[r]
            
            for col, val in raw_row_data.items():
                if col in headers_map:
                    key_name = headers_map[col]
                    processed_row[key_name] = val
            
            if processed_row:
                final_data.append(processed_row)
                
        return final_data

# --- PERMISOS ---
def es_evaluador(user):
    return user.is_staff or user.is_superuser

# --- VISTAS ---

@login_required
def performance_view(request):
    if es_evaluador(request.user):
        return redirect('performance_view_admin')
    else:
        return redirect('performance_view_user')

# --- EN views.py ---

@login_required
@user_passes_test(es_evaluador, login_url='performance_view_user')
def performance_view_admin(request):
    active_cycle = PerformanceReviewCycle.objects.filter(status='active').first()
    history_cycles = PerformanceReviewCycle.objects.filter(status='closed').order_by('-end_date')
    depts_progreso = {}

    if active_cycle:
        revisores = Employee.objects.filter(
            reviews_given__cycle=active_cycle
        ).distinct().select_related('user', 'department')

        for revisor in revisores:
            stats = PerformanceReview.objects.filter(
                cycle=active_cycle, 
                reviewer=revisor
            ).aggregate(
                total=Count('id'),
                # CAMBIO: Filtramos por status='completed'
                completadas=Count('id', filter=Q(status='completed'))
            )
            
            dept_name = revisor.department.name if revisor.department else "General / Otros"
            if dept_name not in depts_progreso:
                depts_progreso[dept_name] = []

            depts_progreso[dept_name].append({
                'nombre': f"{revisor.first_name} {revisor.last_name}",
                'total': stats['total'],
                'completadas': stats['completadas'],
                'porcentaje': round((stats['completadas'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0,
                'terminado': (stats['completadas'] == stats['total'] and stats['total'] > 0)
            })

    context = {
        'active_cycle': active_cycle, 
        'history_cycles': history_cycles,
        'depts_progreso': depts_progreso
    }
    return render(request, 'performance/admin/performance_view_admin.html', context)

@login_required
def performance_view_user(request):
    try:
        current_employee = request.user.employee 
    except AttributeError:
        return render(request, 'performance/user/performance_view_user.html', {'error_msg': 'Sin perfil.'})

    active_cycle = PerformanceReviewCycle.objects.filter(status='active').first()
    
    # 1. EVALUACIONES ASIGNADAS (Ciclo activo: pendientes y realizadas para poder modificar)
    assignments = []
    if active_cycle:
        assignments_query = PerformanceReview.objects.filter(
            cycle=active_cycle,
            reviewer=current_employee
        ).select_related('employee', 'employee__user')
        
        nombre_revisor = f"{current_employee.last_name}, {current_employee.first_name}"
        for review in assignments_query:
            target = review.employee
            if target == current_employee:
                review.relationship_label = "Autoevaluación"
                review.badge_class = "badge-self"
            elif target.responsible == nombre_revisor:
                review.relationship_label = "Colaborador Directo"
                review.badge_class = "badge-sub"
            elif current_employee.responsible == f"{target.last_name}, {target.first_name}":
                review.relationship_label = "Jefe Directo"
                review.badge_class = "badge-boss"
            elif target.responsible == current_employee.responsible:
                review.relationship_label = "Colega (Par)"
                review.badge_class = "badge-peer"
            else:
                review.relationship_label = "Colaborador"
                review.badge_class = "badge-other"
                    
        assignments = assignments_query

    # 2. HISTORIAL - Un recuadro por ciclo cerrado donde fui evaluado
    history_cycles_qs = PerformanceReviewCycle.objects.filter(
        status='closed',
        reviews__employee=current_employee
    ).distinct().annotate(
        reviews_received=Count(
            'reviews',
            filter=Q(reviews__employee=current_employee, reviews__status='completed')
        )
    ).order_by('-end_date')

    total_evaluaciones = history_cycles_qs.count()

    # 3. ÚLTIMA PUNTUACIÓN (promedio del ciclo más reciente)
    ultima_puntuacion = 0
    if history_cycles_qs.exists():
        avg_result = PerformanceReview.objects.filter(
            cycle=history_cycles_qs.first(),
            employee=current_employee,
            status='completed'
        ).aggregate(avg=Avg('rating'))
        ultima_puntuacion = avg_result['avg'] or 0

    # Paginación
    paginator = Paginator(history_cycles_qs, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'active_cycle': active_cycle,
        'assignments': assignments,
        'my_finished_evaluations': page_obj,
        'total_evaluaciones': total_evaluaciones,
        'ultima_puntuacion': ultima_puntuacion,
    }
    return render(request, 'performance/user/performance_view_user.html', context)

# --- CREAR CICLO ---
@login_required
@user_passes_test(es_evaluador)
@require_POST
def create_cycle(request):
    try:
        nombre = request.POST.get('nombre_ciclo')
        anio = request.POST.get('anio_fiscal')
        tipo = request.POST.get('tipo_evaluacion')
        es_360 = request.POST.get('es_360') == 'on'
        
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Error: Sube el archivo Excel.")
            return redirect('performance_view_admin')

        # --- 1. LECTURA DEL EXCEL (Define 'employees_to_evaluate') ---
        try:
            reader = NativeXLSXReader(excel_file)
            rows = reader.get_sheet_data("Empleados")
            
            if not rows:
                messages.error(request, "No se encontró información en la pestaña 'Empleados'.")
                return redirect('performance_view_admin')

            columna_clave = 'número' if 'número' in rows[0] else 'numero'
            lista_ids = []
            for row in rows:
                # Filtro de activos en el Excel
                if 'activo' in row and str(row['activo']).strip().upper() != 'SI':
                    continue
                
                emp_id = str(row.get(columna_clave, '')).strip()
                if emp_id.endswith('.0'): emp_id = emp_id[:-2]
                if emp_id and emp_id.isdigit():
                    lista_ids.append(emp_id)

            # ESTA ES LA VARIABLE QUE FALTABA
            employees_to_evaluate = Employee.objects.filter(
                employee_number__in=lista_ids, 
                is_active=True
            )

            if not employees_to_evaluate.exists():
                messages.warning(request, "No se encontraron empleados en la BD que coincidan con el Excel.")
                return redirect('performance_view_admin')

        except Exception as e:
            messages.error(request, f"Error procesando Excel: {str(e)}")
            return redirect('performance_view_admin')

        # --- 2. CREACIÓN DEL CICLO ---
        ciclo = PerformanceReviewCycle.objects.create(
            name=nombre, year=anio, review_type=tipo, is_360=es_360,
            status='active', scope_type='excel'
        )
        
        created_relations = set()
        reviews_to_create = []

        def add_review(employee_obj, reviewer_obj):
            if employee_obj and reviewer_obj:
                # La llave de control ahora incluye al evaluador
                relation = (employee_obj.id, reviewer_obj.id)
                if relation not in created_relations:
                    reviews_to_create.append(
                        PerformanceReview(
                            cycle=ciclo, 
                            employee=employee_obj, 
                            reviewer=reviewer_obj,
                            status='draft'
                        )
                    )
                    created_relations.add(relation)

        # --- 3. GENERAR RELACIONES ---
        for emp in employees_to_evaluate:
            # A. Autoevaluación (Siempre se crea, sea 360 o no)
            add_review(emp, emp)

            # Identificar al líder directo
            evaluador_lider = None
            if emp.responsible and ',' in emp.responsible:
                partes = emp.responsible.split(',')
                evaluador_lider = Employee.objects.filter(
                    last_name__icontains=partes[0].strip(),
                    first_name__icontains=partes[1].strip()
                ).first()
            
            # B. Relaciones con el Líder
            if evaluador_lider:
                # El Líder siempre evalúa al empleado (Descendente)
                add_review(emp, evaluador_lider)
                
                # Si es 360, el empleado evalúa a su líder (Ascendente)
                if es_360:
                    add_review(evaluador_lider, emp)

            # C. Relaciones entre Pares (Solo en 360)
            if es_360:
                # Buscamos a los que tienen el MISMO jefe que el empleado actual
                # Excluimos al empleado mismo para no duplicar autoevaluación
                companeros = employees_to_evaluate.filter(
                    responsible=emp.responsible
                ).exclude(id=emp.id)
                
                for comp in companeros:
                    # El compañero evalúa al empleado actual
                    add_review(emp, comp)

        # --- 4. GUARDADO ---
        if reviews_to_create:
            PerformanceReview.objects.bulk_create(reviews_to_create)

        messages.success(request, f"Ciclo '{ciclo.name}' creado con {len(reviews_to_create)} evaluaciones.")
        return redirect('performance_view_admin')

    except Exception as e:
        messages.error(request, f"Error crítico: {str(e)}")
        return redirect('performance_view_admin')
        
@login_required
def evaluate_person(request, review_id):
    review = get_object_or_404(PerformanceReview, id=review_id)

    # 2. SEGURIDAD (Se mantiene igual)
    if review.reviewer.user != request.user:
        messages.error(request, "No tienes permiso para ver esta evaluación.")
        return redirect('performance_view_user')

    # 3. PROCESAR EL GUARDADO (Actualizado para usar la nueva tabla)
    if request.method == 'POST':
        try:
            # Lista de claves de competencias que esperas del HTML
            competencias_keys = [
                'comunicacion', 'trabajo_equipo', 'resolucion_conflicto', 'gestion_tiempo', 
                'servicio_cliente', 'iniciativa', 'asistencia', 'puntualidad',
                'toma_decisiones', 'desarrollo_colaboradores'
            ]

            for key in competencias_keys:
                logro_val = request.POST.get(f'logro_{key}')
                
                # Guardamos o actualizamos cada fila en la tabla propia
                PerformanceReviewAnswer.objects.update_or_create(
                    review=review,
                    competencia_key=key,
                    defaults={
                        'logro': int(logro_val) if logro_val and logro_val != '' else None,
                        'comentarios': request.POST.get(f'com_{key}'),
                        'compromisos': request.POST.get(f'comp_{key}'),
                    }
                )

            # Guardamos el Gran Total en el modelo principal
            grand_total = request.POST.get('grand_total_input', '0')
            review.rating = float(grand_total)
            
            # Opcional: Ya no necesitas guardar el JSON en review.comments, 
            # pero puedes dejarlo vacío o guardar una nota general.
            review.comments = "Detalles guardados en tabla relacional" 
            
            review.status = 'completed' 
            review.date_reviewed = timezone.now()
            review.rating = float(request.POST.get('grand_total_input', '0'))
            review.save()

            messages.success(request, f"Evaluación de {review.employee.user.first_name} guardada correctamente.")
            return redirect('performance_view_user')

        except Exception as e:
            messages.error(request, f"Error al guardar: {str(e)}")

    # 4. RENDERIZAR (Actualizado para leer de la tabla propia)
    # Creamos un diccionario 'saved_data' compatible con tu HTML actual
    answers = PerformanceReviewAnswer.objects.filter(review=review)
    saved_data = {}
    for ans in answers:
        saved_data[ans.competencia_key] = {
            'logro': ans.logro,
            'comentarios': ans.comentarios,
            'compromisos': ans.compromisos
        }
    
    
    search_name_evaluado = f"{review.employee.last_name}, {review.employee.first_name}"
    es_lider_evaluado = Employee.objects.filter(responsible__icontains=search_name_evaluado).exists()

    revisor_empleado = request.user.employee
    nombre_evaluado = f"{review.employee.last_name}, {review.employee.first_name}"
    search_name_revisor = f"{revisor_empleado.last_name}, {revisor_empleado.first_name}"
    yo_evaluador_soy_lider = Employee.objects.filter(responsible__icontains=search_name_revisor).exists()
    evaluando_a_mi_jefe = revisor_empleado.responsible == nombre_evaluado
    evaluando_a_mi_subordinado = bool(review.employee.responsible) and search_name_revisor.lower() in review.employee.responsible.lower()

    periodo_texto = "N/A"
    fecha_ref = review.cycle.start_date
    if not fecha_ref:
        fecha_ref = timezone.now()

    mes = fecha_ref.month
    anio = fecha_ref.year

    # Si la evaluación termina en el primer semestre (Enero-Junio), 
    # significa que estamos evaluando el SEGUNDO semestre del año ANTERIOR.
    if mes <= 6:
        periodo_texto = f"JUL - DIC {anio - 1}"
    else:
        # Si es en el segundo semestre (Julio en adelante),
        # evaluamos el PRIMER semestre de ESTE año.
        periodo_texto = f"ENE - JUN {anio}"

    context = {
        'review': review,
        'employee': review.employee, # El empleado a evaluar (puede ser uno mismo)
        'data': saved_data,
        'periodo_texto': periodo_texto,
        'es_lider': es_lider_evaluado,
        'es_autoevaluacion': review.reviewer == review.employee,
        'evaluador_es_lider': yo_evaluador_soy_lider,
        'evaluando_a_mi_jefe': evaluando_a_mi_jefe,
        'evaluando_a_mi_subordinado': evaluando_a_mi_subordinado,
    }
    return render(request, 'performance/user/evaluation.html', context)

@login_required
def my_cycle_history_detail(request, cycle_id):
    try:
        current_employee = request.user.employee
    except AttributeError:
        return redirect('performance_view_user')

    cycle = get_object_or_404(PerformanceReviewCycle, id=cycle_id, status='closed')

    reviews = PerformanceReview.objects.filter(
        cycle=cycle,
        employee=current_employee,
    ).select_related('reviewer', 'reviewer__user').order_by('-status', 'reviewer__last_name')

    nombre_revisor_empleado = f"{current_employee.last_name}, {current_employee.first_name}"
    for review in reviews:
        revisor = review.reviewer
        nombre_revisor = f"{revisor.last_name}, {revisor.first_name}"
        if revisor == current_employee:
            review.relationship_label = "Autoevaluación"
            review.badge_class = "badge-self"
        elif current_employee.responsible == nombre_revisor:
            review.relationship_label = "Jefe Directo"
            review.badge_class = "badge-boss"
        elif bool(revisor.responsible) and nombre_revisor_empleado.lower() in revisor.responsible.lower():
            review.relationship_label = "Colaborador Directo"
            review.badge_class = "badge-sub"
        elif revisor.responsible == current_employee.responsible:
            review.relationship_label = "Colega (Par)"
            review.badge_class = "badge-peer"
        else:
            review.relationship_label = "Colaborador"
            review.badge_class = "badge-other"

    context = {
        'cycle': cycle,
        'reviews': reviews,
        'current_employee': current_employee,
    }
    return render(request, 'performance/user/my_cycle_detail.html', context)


@login_required
@user_passes_test(es_evaluador)
@require_POST
def close_performance_cycle(request, cycle_id):
    cycle = get_object_or_404(PerformanceReviewCycle, id=cycle_id)
    
    # 1. Cambiar estado y poner fecha de finalización
    cycle.status = 'closed'
    cycle.end_date = timezone.now()
    cycle.save()
    
    # 2. (Opcional) Cerrar todas las evaluaciones individuales que quedaron pendientes
    PerformanceReview.objects.filter(cycle=cycle, status='draft').update(status='closed')

    messages.success(request, f"El ciclo '{cycle.name}' ha sido finalizado y movido al historial.")
    return redirect('performance_view_admin')