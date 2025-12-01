# apps/org_chart/utils.py

from apps.employee.models import JobPosition, Employee

def get_org_chart_data():
    # 1. Encontrar la posición raíz (el nivel más alto, reports_to es NULL)
    try:
        root_position = JobPosition.objects.get(reports_to__isnull=True, level=1)
    except JobPosition.DoesNotExist:
        # Manejar caso sin posición raíz
        return None

    # 2. Construir la estructura recursiva
    def build_tree(position):
        # 2a. Obtener el empleado o marcar como vacante
        try:
            employee = Employee.objects.get(job_position=position)
            name = f"{employee.first_name} {employee.last_name}"
            title = position.title
            photo_url = employee.photo.url if employee.photo else '/static/default_photo.png'
            is_vacant = False
        except Employee.DoesNotExist:
            # Caso de Posición Vacante
            name = "Vacante"
            title = position.title
            photo_url = '/static/vacant_icon.png'
            is_vacant = True

        node = {
            'id': position.pk,
            'name': name,
            'title': title,
            'photo': photo_url,
            'is_vacant': is_vacant,
            'children': []
        }

        # 2b. Buscar los puestos que reportan a este puesto
        subordinate_positions = position.subordinates.all().order_by('level', 'title')

        for sub_position in subordinate_positions:
            node['children'].append(build_tree(sub_position))

        return node

    return build_tree(root_position)