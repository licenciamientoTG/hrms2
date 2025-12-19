(function(){
  const input = document.getElementById('users-search');
  if (!input) return;

  const debounce = (fn, ms=1000) => { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; };

  function go(){
    const url  = new URL(window.location.href);
    const term = (input.value || '').trim();

    if (term) url.searchParams.set('q', term);
    else url.searchParams.delete('q');

    // volver a la primera página para ver todos los matches
    url.searchParams.delete('page');

    // conserva otros params (page_size, etc.) automáticamente
    window.location.assign(url);
  }

  // Evita submit tradicional y usa nuestro go()
  if (input.form) {
    input.form.addEventListener('submit', (e) => { e.preventDefault(); go(); });
  }

  // Sólo dispara con Enter; Esc borra y busca vacío
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      go();
    } else if (e.key === 'Escape') {
      input.value = '';
      go();
    }
  });
})();

// --- Activar/Desactivar usuario (delegación restaurada)
(function(){
  const table = document.getElementById('admin-users-table');
  if (!table) return;

  const toggleUrl = table.dataset.toggleUrl;

  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  const csrfToken = getCookie('csrftoken');

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-toggle-status');
    if (!btn) return;              // no es el botón
    if (!toggleUrl) return;        // falta URL
    const userId = btn.dataset.userId;
    if (!userId) return;

    btn.disabled = true;
    try {
      const res = await fetch(toggleUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: 'user_id=' + encodeURIComponent(userId)
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (data.status !== 'ok') throw new Error('Respuesta no OK');

      const row   = document.getElementById('row-' + userId);
      const badge = row?.querySelector('.status-badge');

      if (data.is_active) {
        badge?.classList.remove('bg-secondary');
        badge?.classList.add('bg-success');
        if (badge) badge.textContent = 'Activo';
        btn.textContent = 'Desactivar';
      } else {
        badge?.classList.remove('bg-success');
        badge?.classList.add('bg-secondary');
        if (badge) badge.textContent = 'Inactivo';
        btn.textContent = 'Activar';
      }
    } catch (err) {
      console.error(err);
      alert('No se pudo cambiar el estado.');
    } finally {
      btn.disabled = false;
    }
  });
})();

function toggleStatus(userId) {
  fetch(toggleUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrfToken
    },
    body: "user_id=" + userId
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === "ok") {
      const row = document.getElementById("row-" + userId);
      const statusSpan = row.querySelector(".status");
      const button = row.querySelector("button");

      if (data.is_active) {
        statusSpan.textContent = "✅ Activo";
        button.textContent = "Desactivar";
      } else {
        statusSpan.textContent = "🚫 Inactivo";
        button.textContent = "Activar";
      }
    }
  });
}

// Filtro de permisos en el modal de crear grupo
(function(){
    const searchInput = document.getElementById('searchPermissions');
    if (!searchInput) return;

    searchInput.addEventListener('keyup', function(e) {
        const term = e.target.value.toLowerCase();
        // Seleccionamos todos los contenedores de los permisos (los col-md-6)
        const items = document.querySelectorAll('.perm-item');

        items.forEach(function(item) {
            // Buscamos el texto dentro del label
            const label = item.querySelector('label').textContent.toLowerCase();
            
            // Si el término está incluido, mostramos; si no, ocultamos
            if (label.includes(term)) {
                item.style.display = ''; // Restaura el display original (block/flex)
            } else {
                item.style.display = 'none';
            }
        });
    });
})();

// 1. Script para eliminar grupo (ya lo tenías)
function confirmarEliminar(groupId, groupName) {
    if(confirm("¿Estás seguro de eliminar el grupo '" + groupName + "'? \n\nEsto quitará los permisos a TODOS los usuarios que pertenezcan a este grupo.")) {
        var form = document.getElementById('deleteGroupForm');
        // Ajusta la URL si es necesario
        form.action = "/users/groups/delete/" + groupId + "/"; 
        form.submit();
    }
}

// 2. FUNCIÓN DE FILTRADO REUTILIZABLE
// Esta función sirve para los 3 buscadores
function configurarFiltro(inputId, contenedorId, contadorId = null) {
    const input = document.getElementById(inputId);
    const contenedor = document.getElementById(contenedorId);
    
    if (!input || !contenedor) return; // Si no existen en el HTML, no hace nada

    const items = contenedor.getElementsByClassName('item-filtro');

    input.addEventListener('keyup', function(e) {
        const texto = e.target.value.toLowerCase();
        let visibles = 0;

        Array.from(items).forEach(function(item) {
            // Buscamos el texto dentro del item (incluye etiquetas label, small, etc.)
            const contenido = item.innerText.toLowerCase();
            
            if (contenido.includes(texto)) {
                item.style.display = ''; // Mostrar (valor por defecto)
                visibles++;
            } else {
                item.style.display = 'none'; // Ocultar
            }
        });

        // Si hay un elemento para mostrar el contador, lo actualizamos
        if (contadorId) {
            const contadorElem = document.getElementById(contadorId);
            if (contadorElem) {
                contadorElem.innerText = texto.length > 0 ? visibles + " resultados" : "";
            }
        }
    });
}

// 3. Inicializar los filtros cuando cargue la página
document.addEventListener('DOMContentLoaded', function() {
    // Filtro del Modal de Crear Grupo
    configurarFiltro('filtroModal', 'contenedorModal', 'contadorModal');
    
    // Filtro de Permisos Individuales (Columna Izquierda)
    configurarFiltro('filtroPermisosIndiv', 'contenedorPermisosIndiv');

    // Filtro de Grupos (Columna Derecha)
    configurarFiltro('filtroGrupos', 'contenedorGrupos');
});

function confirmarEliminar(groupId, groupName) {
    Swal.fire({
        title: '¿Estás seguro?',
        text: `Estás a punto de eliminar el grupo "${groupName}". Esta acción quitará los permisos a todos los usuarios que pertenezcan a este grupo.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Si confirma, enviamos el formulario oculto
            var form = document.getElementById('deleteGroupForm');
            form.action = "/users/groups/delete/" + groupId + "/"; 
            form.submit();
        }
    });
}

// 3. Función de búsqueda (Filtros)
function configurarFiltro(inputId, contenedorId, contadorId = null) {
    const input = document.getElementById(inputId);
    const contenedor = document.getElementById(contenedorId);
    if (!input || !contenedor) return;

    const items = contenedor.getElementsByClassName('item-filtro');

    input.addEventListener('keyup', function(e) {
        const texto = e.target.value.toLowerCase();
        let visibles = 0;

        Array.from(items).forEach(function(item) {
            const contenido = item.innerText.toLowerCase();
            if (contenido.includes(texto)) {
                item.style.display = '';
                visibles++;
            } else {
                item.style.display = 'none';
            }
        });

        if (contadorId) {
            const contadorElem = document.getElementById(contadorId);
            if (contadorElem) contadorElem.innerText = texto.length > 0 ? visibles + " resultados" : "";
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    configurarFiltro('filtroModal', 'contenedorModal', 'contadorModal');
    configurarFiltro('filtroPermisosIndiv', 'contenedorPermisosIndiv');
    configurarFiltro('filtroGrupos', 'contenedorGrupos');
});

