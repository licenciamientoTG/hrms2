document.addEventListener("DOMContentLoaded", function() {
    // Seleccionamos todos los enlaces del sidebar que tengan un badge dentro
    const links = document.querySelectorAll('.sidebar-link');

    links.forEach(link => {
        link.addEventListener('click', function(e) {
            // Buscamos si este enlace tiene un badge con notificaciones
            const badge = this.querySelector('.badge.bg-danger');
            
            if (badge) {
                // Mapeo de URLs a nombres de módulos (debes ajustar esto según tus URLs y modules en BD)
                let moduleName = null;
                const href = this.getAttribute('href');

                if (href.includes('/users/')) moduleName = 'usuarios';
                else if (href.includes('/news/')) moduleName = 'noticias';
                else if (href.includes('/recognitions/')) moduleName = 'comunicados';
                else if (href.includes('/forms_requests/')) moduleName = 'constancias';
                else if (href.includes('/surveys/')) moduleName = 'encuestas';
                else if (href.includes('/courses/')) moduleName = 'cursos';
                else if (href.includes('/org-chart/')) moduleName = 'organigrama';
                else if (href.includes('/vacations/')) moduleName = 'vacaciones';
                else if (href.includes('/objectives/')) moduleName = 'objetivos';
                else if (href.includes('/archive/')) moduleName = 'archivo';
                else if (href.includes('/onboarding/')) moduleName = 'onboarding';
                else if (href.includes('/documents/')) moduleName = 'mis_documentos';
                else if (href.includes('/job-offers/')) moduleName = 'vacantes';
                else if (href.includes('/policies/')) moduleName = 'politicas';
                else if (href.includes('/career-plan/')) moduleName = 'plan_carrera';
                else if (href.includes('/staff-requisitions/')) moduleName = 'requisiciones';

                if (moduleName) {
                    // Llamada asíncrona para marcar como leído (no esperamos la respuesta para navegar)
                    // Usamos navigator.sendBeacon si es posible para asegurar el envío al cambiar de página
                    const url = `/notifications/api/mark-module-read/${moduleName}/`;
                    const csrfToken = getCookie('csrftoken'); // Asegúrate de tener esta función disponible

                    // Opción A: fetch (puede cancelarse si la página cambia muy rápido)
                    fetch(url, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    // Ocultamos el badge visualmente de inmediato
                    badge.style.display = 'none';
                }
            }
        });
    });

    // Helper para CSRF
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});