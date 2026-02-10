from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import path
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponseForbidden
from .models import RecognitionCategory, Recognition, RecognitionComment, RecognitionMedia
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.utils.timezone import now
from django.utils.timesince import timesince
from .models import RecognitionLike
from django.db.models import Prefetch, Count, Exists, OuterRef, Q
from .emails import send_recognition_email
from django.db import transaction
from datetime import datetime
from django.utils.timezone import make_aware, get_current_timezone
from .services import publish_recognition_if_due
from apps.employee.models import Employee
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group
from apps.employee.models import Employee 
from departments.models import Department
from apps.employee.models import JobPosition

# esta vista te redirige a las vistas de usuario y administrador
@login_required
def recognition_dashboard(request):
    if request.user.is_staff:
        return redirect('recognition_dashboard_admin')
    else:
        return redirect('recognition_dashboard_user')

@login_required
@user_passes_test(lambda u: u.is_staff)
def recognition_dashboard_admin(request):
    # --- 1. Lógica de Guardado (POST) ---
    if request.method == "POST":
        recipients_ids = request.POST.getlist('recipients')
        category_id    = request.POST.get('category')
        message        = (request.POST.get('message') or '').strip()
        email_subject  = (request.POST.get('email_subject') or '').strip()
        files          = request.FILES.getlist('media')
        notify_email   = bool(request.POST.get('notify_email'))
        email_channels = request.POST.getlist('email_channels') if notify_email else []
        publish_at     = _parse_datetime_local(request.POST.get('publish_at'))
        es_prioritario = request.POST.get('is_priority') == 'on'

        errors = []
        if len(recipients_ids) > MAX_RECIPIENTS:
            errors.append(_("Máximo %(n)s colaboradores.") % {'n': MAX_RECIPIENTS})

        category = None
        if not category_id:
            errors.append(_("Selecciona una categoría."))
        else:
            category = get_object_or_404(RecognitionCategory, pk=category_id) # Admin ve todas, incluso inactivas si quiere, o filtra is_active=True

        if files:
            files = files[:MAX_IMAGES_PER_POST]
            bad = [f.name for f in files if not _is_image_ok(f)]
            if bad:
                errors.append(_("Imágenes inválidas: %(lst)s") % {"lst": ", ".join(bad)})

        if errors:
            for e in errors: messages.error(request, e)
        else:
            # Guardar
            with transaction.atomic():
                # Lógica de audiencia
                target_groups_input = request.POST.getlist('target_groups')
                is_public = 'todos' in target_groups_input or not target_groups_input
                
                rec = Recognition.objects.create(
                    author=request.user,
                    category=category,
                    message=message,
                    email_subject=email_subject,
                    publish_at=publish_at,
                    notify_email=notify_email,
                    notify_push=True,
                    email_channels=email_channels or None,
                    status="scheduled" if publish_at else "draft",
                    is_public=is_public,
                    is_priority=es_prioritario
                )
                
                # Si no es público, asignamos los grupos específicos
                if not is_public and target_groups_input:
                    groups = Group.objects.filter(name__in=target_groups_input)
                    rec.target_groups.set(groups)

                employees = Employee.objects.filter(id__in=recipients_ids, is_active=True).exclude(user_id__isnull=True)
                users = User.objects.filter(id__in=employees.values_list('user_id', flat=True), is_active=True)
                rec.recipients.add(*users)

                for f in files:
                    RecognitionMedia.objects.create(recognition=rec, file=f)

            # Publicar
            published_now = publish_recognition_if_due(rec)
            
            if published_now:
                messages.success(request, "¡Comunicado publicado exitosamente!")
            else:
                messages.success(request, "Comunicado programado.")

        # IMPORTANTE: Redirigir a la misma vista de admin para evitar reenvíos
        return redirect('recognition_dashboard_admin')

    q = (request.GET.get("q") or "").strip()

    qs = RecognitionCategory.objects.all().order_by('order', 'title')
    if q:
        qs = qs.filter(title__icontains=q)  # filtra por título

    paginator   = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
    people = Employee.objects.filter(is_active=True)

    context = {
        "categories": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "q": q, 
        'people': people,
    }
    return render(request, "recognitions/admin/recognition_dashboard_admin.html", context)


# esta vista es para el usuario
User = get_user_model()

MAX_RECIPIENTS = 30
MAX_IMAGES_PER_POST = 10
MAX_MB = 10
PAGE_SIZE = 12

def _is_image_ok(f):
    return f.content_type.startswith('image/') and f.size <= MAX_MB * 1024 * 1024

def _parse_datetime_local(raw):
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
        return make_aware(naive, get_current_timezone())
    except Exception:
        return None

@login_required
@require_http_methods(["GET", "POST"])
def recognition_dashboard_user(request):
    # --- POST: crear / programar comunicado ---
    if request.method == "POST" and not request.user.has_perm('recognitions.add_recognition'):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        messages.error(request, "No tienes permiso para enviar comunicado.")
        return redirect('recognition_dashboard_user')

    if request.method == "POST":
        recipients_ids = request.POST.getlist('recipients')
        category_id    = request.POST.get('category')
        message        = (request.POST.get('message') or '').strip()
        files          = request.FILES.getlist('media')
        notify_email   = bool(request.POST.get('notify_email'))
        email_channels = request.POST.getlist('email_channels') if notify_email else []
        publish_at     = _parse_datetime_local(request.POST.get('publish_at'))  # 👈 nuevo

        # Validaciones
        errors = []
        if len(recipients_ids) > MAX_RECIPIENTS:
            errors.append(_("Máximo %(n)s colaboradores.") % {'n': MAX_RECIPIENTS})

        category = None
        if not category_id:
            errors.append(_("Selecciona una categoría."))
        else:
            category = get_object_or_404(RecognitionCategory, pk=category_id, is_active=True)

        if files:
            files = files[:MAX_IMAGES_PER_POST]
            bad = [f.name for f in files if not _is_image_ok(f)]
            if bad:
                errors.append(_("Hay imágenes no válidas o mayores a %(n)s MB: %(lst)s") %
                              {"n": MAX_MB, "lst": ", ".join(bad)})

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('recognition_dashboard_user')

        # Guardar todo (atómico)
        with transaction.atomic():
            rec = Recognition.objects.create(
                author=request.user,
                category=category,
                message=message,
                publish_at=publish_at,
                notify_email=notify_email,
                notify_push=True,                 # si más tarde lo expones en el form, cámbialo aquí
                email_channels=email_channels or None,
                status="scheduled" if publish_at else "draft",
            )
            users = User.objects.filter(id__in=recipients_ids, is_active=True)
            rec.recipients.add(*users)
            for f in files:
                RecognitionMedia.objects.create(recognition=rec, file=f)

        # Publicar si ya toca (el servicio también envía el correo una sola vez)
        published_now = publish_recognition_if_due(rec)

        if published_now:
            messages.success(
                request,
                _("¡Comunicado publicado!") if not notify_email
                else _("¡Comunicado publicado y correo enviado!")
            )
        else:
            messages.success(request, _("Comunicado programado para publicarse en su fecha."))

        return redirect('recognition_dashboard_user')

    # --- GET: feed con scroll infinito (solo publicados) ---
    page = int(request.GET.get('page', 1))

    user_groups = request.user.groups.all()
    
    base_qs = (
        Recognition.objects
        .select_related('author', 'category')
        .filter(published_at__isnull=False)            # solo publicados
        .filter(
            Q(is_public=True) | 
            Q(target_groups__in=user_groups) | 
            Q(recipients=request.user) |
            Q(target_groups__isnull=True, is_public=False) # Comunicados antiguos
        )
        .distinct()
        .annotate(
            like_count=Count('likes_rel', distinct=True),
            my_liked=Exists(
                RecognitionLike.objects.filter(recognition=OuterRef('pk'), user=request.user)
            ),
        )
        .prefetch_related(
            'recipients', 'media',
            Prefetch(
                'comments',
                queryset=RecognitionComment.objects.select_related('author').order_by('created_at')
            )
        )
        .order_by('-published_at')
    )

    paginator = Paginator(base_qs, PAGE_SIZE)
    page_obj  = paginator.get_page(page)

    ctx = {
        "people": User.objects.filter(is_active=True)
                              .exclude(id=request.user.id)
                              .order_by('first_name', 'last_name', 'username'),
        "categories": RecognitionCategory.objects.filter(is_active=True)
                                                .order_by('order', 'title'),
        "feed": page_obj.object_list,
        "has_next": page_obj.has_next(),
        "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('recognitions/user/_cards.html', ctx, request=request)
        return JsonResponse({"html": html, "has_next": ctx["has_next"], "next_page": ctx["next_page"]})

    return render(request, 'recognitions/user/recognition_dashboard_user.html', ctx)
    
class AdminOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

class CategoryListView(LoginRequiredMixin, AdminOnlyMixin, ListView):
    template_name = "recognitions/admin/recognition_dashboard_admin.html"   # tu tabla
    model = RecognitionCategory
    context_object_name = "categories"
    paginate_by = 20

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_create(request):
    ctx = {"errors": {}, "initial": {}}

    if request.method == "POST":
        # recoger datos
        title  = request.POST.get("title", "").strip()
        points = request.POST.get("points", "0").strip()
        color_hex = request.POST.get("color_hex", "#1E3361").strip()
        confetti_enabled = request.POST.get("confetti_enabled") == "on"
        show_points = request.POST.get("show_points") == "on"
        order = request.POST.get("order", "0").strip()
        is_active = request.POST.get("is_active") == "on"
        cover_image = request.FILES.get("cover_image")

        # guardar para repoblar en caso de error
        ctx["initial"] = {
            "title": title, "points": points, "color_hex": color_hex,
            "confetti_enabled": confetti_enabled, "show_points": show_points,
            "order": order, "is_active": is_active
        }

        # validaciones mínimas
        if not title:
            ctx["errors"]["title"] = "El nombre es obligatorio."
        try:
            points_int = int(points)
            if points_int < 0: raise ValueError
        except ValueError:
            ctx["errors"]["points"] = "Puntos debe ser un entero ≥ 0."
        try:
            order_int = int(order)
            if order_int < 0: raise ValueError
        except ValueError:
            ctx["errors"]["order"] = "Orden debe ser un entero ≥ 0."
        if not color_hex.startswith("#") or len(color_hex) != 7:
            ctx["errors"]["color_hex"] = "Usa un color en formato #RRGGBB."

        if not ctx["errors"]:
            obj = RecognitionCategory(
                title=title,
                points=points_int,
                color_hex=color_hex,
                confetti_enabled=confetti_enabled,
                show_points=show_points,
                order=order_int,
                is_active=is_active,
            )
            if cover_image:
                obj.cover_image = cover_image
            obj.save()
            return redirect("recognition_dashboard")  # lista

    return render(request, "recognitions/admin/recognition_category_create.html", ctx)


class CategoryUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    model = RecognitionCategory
    template_name = "recognitions/admin/recognition_category_edit.html" 
    fields = [
        "title", "color_hex",
        "confetti_enabled",
        "cover_image", "is_active",
    ]
    success_url = reverse_lazy("recognition_dashboard")  # o "recognition_dashboard_admin"

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def category_delete_post(request, pk):
    if request.method != "POST":
        return redirect("recognition_dashboard")
    obj = get_object_or_404(RecognitionCategory, pk=pk)
    try:
        obj.delete()
    except ProtectedError:
        messages.error(
            request,
            "No se puede eliminar porque ya fue utilizada. Puedes desactivarla para impedir su uso futuro."
        )
    return redirect("recognition_dashboard")

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
@require_POST
def category_toggle_active(request, pk):
    obj = get_object_or_404(RecognitionCategory, pk=pk)

    # Si viene desde el SweetAlert (cuando no se puede borrar), desactiva sí o sí
    force_deactivate = request.POST.get("force_deactivate") == "1"

    if force_deactivate:
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active"])
            
        else:
            # Ya estaba desactivada: no la actives por error
            messages.info(request, "La categoría ya estaba desactivada.")
    else:
        # Toggle normal (botón “Activar/Desactivar” del menú)
        obj.is_active = not obj.is_active
        obj.save(update_fields=["is_active"])


    return redirect("recognition_dashboard")

# Crear comentario
@login_required
@require_POST
def recognition_comment_create(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)
    body = (request.POST.get('body') or '').strip()
    if not body:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Texto vacío.'}, status=400)
        messages.error(request, 'El comentario no puede estar vacío.')
        return redirect('recognition_dashboard_user')

    c = RecognitionComment.objects.create(
        recognition=rec,
        author=request.user,
        body=body
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            "recognitions/user/_comment.html",   # ← tu parcial
            {"c": c, "request": request},
            request=request
        )
        count = rec.comments.count()
        return JsonResponse({'ok': True, 'html': html, 'count': count})

    return redirect('recognition_dashboard_user')

# Borrar comentario (autor o moderador con permiso delete)
@login_required
@require_http_methods(["POST"])
def recognition_comment_delete(request, pk, cid):
    c = get_object_or_404(RecognitionComment, pk=cid, recognition_id=pk)

    can_delete = (
        request.user == c.author or
        request.user.has_perm('recognitions.delete_recognitioncomment')  # 👈 permiso built-in
    )
    if not can_delete:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return HttpResponseForbidden("No autorizado")

    c.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        count = RecognitionComment.objects.filter(recognition_id=pk).count()
        return JsonResponse({"ok": True, "count": count})

    return redirect('recognition_dashboard_user')


# toggle
@login_required
@require_POST
def recognition_like_toggle(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)
    obj, created = RecognitionLike.objects.get_or_create(recognition=rec, user=request.user)
    liked = created
    if not created:
        obj.delete()
    count = RecognitionLike.objects.filter(recognition=rec).count()
    return JsonResponse({'ok': True, 'liked': liked, 'count': count})

# lista
# helpers
def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""

def _display_name(user) -> str:
    fn = _first_token(getattr(user, "first_name", ""))
    ln = _first_token(getattr(user, "last_name", ""))
    full = f"{fn} {ln}".strip()
    return full or user.get_username()

@login_required
@require_GET
def recognition_likes_list(request, pk):
    rec = get_object_or_404(Recognition, pk=pk)

    # Usamos el modelo intermedio RecognitionLike
    qs = (RecognitionLike.objects
          .filter(recognition=rec)
          .select_related("user")
          .order_by("-created_at"))

    items = [{
        "name": _display_name(like.user),
        "liked_at": "",
    } for like in qs]

    return JsonResponse({
        "rec_id": rec.id,
        "title": (rec.message or "")[:60],
        "count": qs.count(),
        "items": items,
    })
 
@login_required
@user_passes_test(lambda u: u.is_staff)
def recognition_scheduled_list(request):
    """Devuelve HTML parcial con la lista de comunicados programados para el futuro"""
    now = timezone.now()
    scheduled = Recognition.objects.filter(
        publish_at__gt=now,  # Fecha futura
        status='scheduled'   # Opcional si usas status
    ).order_by('publish_at')

    return render(request, 'recognitions/admin/_scheduled_list.html', {'scheduled': scheduled})

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def recognition_delete_scheduled(request, pk):
    """Permite cancelar/eliminar un comunicado agendado"""
    rec = get_object_or_404(Recognition, pk=pk)
    rec.delete()
    return JsonResponse({'ok': True})

@staff_member_required  # O el decorador de permisos que uses
def group_management_view(request):
    # Nombres exactos de tus grupos
    nombres_grupos = ["Corporativo", "Estaciones", "Estaciones Juárez"]
    for nombre in nombres_grupos:
        Group.objects.get_or_create(name=nombre)
    
    # Filtramos solo estos 3 grupos para mostrarlos
    grupos = Group.objects.filter(name__in=nombres_grupos)
    
    context = {
        "grupos": grupos
    }
    return render(request, "recognitions/admin/group_list.html", context)

@staff_member_required
def editar_miembros_grupo(request, group_id):
    grupo = get_object_or_404(Group, id=group_id)
    
    if request.method == 'POST':
        # 1. Obtener IDs de los 3 selectores
        user_ids = request.POST.getlist('usuarios_seleccionados')
        dept_ids = request.POST.getlist('departamentos_seleccionados')
        puesto_ids = request.POST.getlist('puestos_seleccionados')
        
        # 2. Buscar los objetos User correspondientes
        # A) Seleccionados manualmente
        users_directos = User.objects.filter(id__in=user_ids)
        
        # B) Por Departamento (Buscamos empleados en esos depts y obtenemos sus usuarios)
        # Nota: Filtramos user__isnull=False para ignorar empleados sin usuario de sistema
        users_por_dept = User.objects.filter(
            employee__department_id__in=dept_ids, 
            employee__is_active=True
        )
        
        # C) Por Puesto
        users_por_puesto = User.objects.filter(
            employee__job_position_id__in=puesto_ids,
            employee__is_active=True
        )
        
        # 3. UNIÓN DE CONJUNTOS (El operador | elimina duplicados automáticamente)
        # Esto junta las 3 listas y deja solo 1 registro por persona
        lista_final_usuarios = users_directos | users_por_dept | users_por_puesto
        
        # .distinct() asegura que no haya duplicados a nivel base de datos
        grupo.user_set.set(lista_final_usuarios.distinct())
        
        messages.success(request, f'Grupo "{grupo.name}" actualizado. Total miembros: {grupo.user_set.count()}')
        return redirect('administrar_grupos')

    # GET: Preparamos los datos para el formulario
    usuarios_disponibles = User.objects.filter(is_active=True).select_related('employee').order_by('first_name')
    departamentos = Department.objects.all().order_by('name')
    puestos_unicos = JobPosition.objects.values_list('title', flat=True).distinct().order_by('title') 

    # Obtenemos los miembros actuales para mostrarlos en la tabla
    miembros_actuales = grupo.user_set.all().select_related('employee').order_by('first_name')
    
    context = {
        'grupo': grupo,
        'usuarios_disponibles': usuarios_disponibles,
        'departamentos': departamentos,
        'puestos': puestos_unicos,
        'miembros_actuales': miembros_actuales
    }

    return render(request, 'recognitions/admin/edit_members.html', context)

@login_required
def check_priority_announcement(request):
    """Busca el comunicado prioritario de la última semana no aceptado."""
    user_groups = request.user.groups.all()
    
    # 1. Definimos el límite de tiempo a 7 días
    hace_una_semana = timezone.now() - timezone.timedelta(days=7)
    
    # 2. Aplicamos el filtro de fecha
    announcement = Recognition.objects.filter(
        is_priority=True,
        published_at__lte=timezone.now(),
        published_at__gte=hace_una_semana  # Filtra comunicados de los últimos 7 días
    ).filter(
        Q(is_public=True) | Q(target_groups__in=user_groups) | Q(recipients=request.user)
    ).exclude(
        priority_viewed_by=request.user
    ).order_by('-published_at').first()

    if announcement:
        # Lógica para obtener la imagen
        image_url = None
        if announcement.image:
            image_url = announcement.image.url
        elif announcement.media.exists():
            image_url = announcement.media.first().file.url

        return JsonResponse({
            'has_priority': True,
            'id': announcement.id,
            'title': announcement.category.title,
            'message': announcement.message,
            'color': announcement.category.color_hex,
            'image_url': image_url
        })
        
    return JsonResponse({'has_priority': False})

@login_required
@require_POST
def mark_priority_read(request, pk):
    """Agrega al usuario a la lista de lectura del comunicado."""
    announcement = get_object_or_404(Recognition, pk=pk)
    announcement.priority_viewed_by.add(request.user)
    return JsonResponse({'ok': True})