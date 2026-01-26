import zipfile
import xml.etree.ElementTree as ET
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.employee.models import Employee
from apps.performance.models import PerformanceReviewCycle, PerformanceReview
from django.db.models import Q

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

@login_required
@user_passes_test(es_evaluador, login_url='performance_view_user')
def performance_view_admin(request):
    active_cycle = PerformanceReviewCycle.objects.filter(status='active').first()
    history_cycles = PerformanceReviewCycle.objects.filter(status='closed').order_by('-end_date')
    context = {'active_cycle': active_cycle, 'history_cycles': history_cycles}
    return render(request, 'performance/admin/performance_view_admin.html', context)

@login_required
def performance_view_user(request):
    try:
        current_employee = request.user.employee 
    except AttributeError:
        return render(request, 'performance/user/performance_view_user.html', {'error_msg': 'Sin perfil.'})

    active_cycle = PerformanceReviewCycle.objects.filter(status='active').first()
    
    # Lista de personas a las que YO tengo que evaluar (incluyéndome a mí mismo si aplica)
    assignments = [] 

    if active_cycle:
        # Buscamos en la tabla PerformanceReview donde el 'reviewer' sea el usuario actual
        assignments = PerformanceReview.objects.filter(
            cycle=active_cycle
        ).filter(
            Q(reviewer=current_employee) | Q(employee=current_employee)
        ).select_related('employee', 'employee__user').distinct()

    context = {
        'active_cycle': active_cycle,
        'assignments': assignments,  # <--- ESTA ES LA VARIABLE NUEVA CLAVE
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

        employees_to_evaluate = []

        try:
            reader = NativeXLSXReader(excel_file)
            rows = reader.get_sheet_data("Empleados")
            
            if not rows:
                messages.error(request, "No se encontró la columna 'Número' en las filas visibles del Excel.")
                return redirect('performance_view_admin')

            # Buscar columna clave
            columna_clave = 'número'
            if columna_clave not in rows[0]:
                if 'numero' in rows[0]: columna_clave = 'numero'
            
            lista_ids = []
            for row in rows:
                # 1. Filtro "Activo" (SI/NO) del Excel
                if 'activo' in row:
                    val_activo = str(row['activo']).strip().upper()
                    if val_activo != 'SI':
                        continue
                
                # 2. Obtener ID
                emp_id = str(row.get(columna_clave, '')).strip()
                if emp_id.endswith('.0'):
                    emp_id = emp_id[:-2]
                
                if emp_id and emp_id.isdigit():
                    lista_ids.append(emp_id)

            employees_to_evaluate = Employee.objects.filter(
                employee_number__in=lista_ids, 
                is_active=True
            )

            if not employees_to_evaluate.exists():
                messages.warning(request, f"Se leyeron {len(lista_ids)} registros visibles, pero ninguno coincide con la BD.")
                return redirect('performance_view_admin')

        except Exception as e:
            messages.error(request, f"Error procesando Excel: {str(e)}")
            return redirect('performance_view_admin')

        # Crear Ciclo
        ciclo = PerformanceReviewCycle.objects.create(
            name=nombre, year=anio, review_type=tipo, is_360=es_360,
            status='active', scope_type='excel'
        )
        
        # Crear Evaluaciones
        reviews_created = [
            PerformanceReview(cycle=ciclo, employee=emp, reviewer=emp, status='draft') 
            for emp in employees_to_evaluate
        ]
        PerformanceReview.objects.bulk_create(reviews_created)

        messages.success(request, f"Éxito: Se crearon {len(reviews_created)} evaluaciones (Filas ocultas ignoradas).")
        return redirect('performance_view_admin')

    except Exception as e:
        messages.error(request, f"Error crítico: {str(e)}")
        return redirect('performance_view_admin')

        
@login_required
def evaluate_person(request, review_id):
    # 1. Obtener la evaluación específica
    review = get_object_or_404(PerformanceReview, id=review_id)

    # 2. SEGURIDAD: Verificar que el usuario logueado es el revisor asignado
    # (Si es autoevaluación, el reviewer debe ser él mismo en la BD)
    if review.reviewer.user != request.user:
        messages.error(request, "No tienes permiso para ver esta evaluación.")
        return redirect('performance_view_user')

    # 3. PROCESAR EL GUARDADO (POST)
    if request.method == 'POST':
        try:
            # Recopilamos los datos del formulario "Excel"
            evaluation_data = {
                'comunicacion': {
                    'comentarios': request.POST.get('com_comunicacion'),
                    'compromisos': request.POST.get('comp_comunicacion'),
                    'logro': request.POST.get('logro_comunicacion') 
                },
                'equipo': {  # OJO: en el HTML usamos 'equipo', asegúrate que coincida
                    'comentarios': request.POST.get('com_equipo'),
                    'compromisos': request.POST.get('comp_equipo'),
                    'logro': request.POST.get('logro_equipo')
                },
                'conflicto': {
                    'comentarios': request.POST.get('com_conflicto'),
                    'compromisos': request.POST.get('comp_conflicto'),
                    'logro': request.POST.get('logro_conflicto')
                },
                'tiempo': {
                    'comentarios': request.POST.get('com_tiempo'),
                    'compromisos': request.POST.get('comp_tiempo'),
                    'logro': request.POST.get('logro_tiempo')
                },
                'servicio': {
                    'comentarios': request.POST.get('com_servicio'),
                    'compromisos': request.POST.get('comp_servicio'),
                    'logro': request.POST.get('logro_servicio')
                },
                'iniciativa': {
                    'comentarios': request.POST.get('com_iniciativa'),
                    'compromisos': request.POST.get('comp_iniciativa'),
                    'logro': request.POST.get('logro_iniciativa')
                },
                'asistencia': {
                    'comentarios': request.POST.get('com_asistencia'),
                    'compromisos': request.POST.get('comp_asistencia'),
                    'logro': request.POST.get('logro_asistencia')
                },
                'puntualidad': {
                    'comentarios': request.POST.get('com_puntualidad'),
                    'compromisos': request.POST.get('comp_puntualidad'),
                    'logro': request.POST.get('logro_puntualidad')
                }
            }

            # Guardamos el Gran Total calculado
            grand_total = request.POST.get('grand_total_input', '0')
            
            # Actualizamos el modelo
            review.rating = float(grand_total)
            # Guardamos todo el detalle como JSON en el campo comments
            review.comments = json.dumps(evaluation_data, ensure_ascii=False) 
            review.status = 'completed' # O 'closed' si quieres cerrarlo directo
            review.date_reviewed = timezone.now()
            review.save()

            messages.success(request, f"Evaluación de {review.employee.user.first_name} guardada correctamente.")
            return redirect('performance_view_user')

        except Exception as e:
            messages.error(request, f"Error al guardar: {str(e)}")

    # 4. RENDERIZAR (GET)
    # Convertimos los comentarios guardados de JSON a Dict para rellenar el formulario si ya existe
    saved_data = {}
    if review.comments and review.comments.startswith('{'):
        try:
            saved_data = json.loads(review.comments)
        except:
            pass
    
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
        'periodo_texto': periodo_texto
    }
    return render(request, 'performance/user/evaluation.html', context)