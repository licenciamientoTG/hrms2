document.addEventListener('DOMContentLoaded', () => {
    // Hook mínimo para poblar el modal de detalle desde la fila clicada
    document.querySelectorAll('.btn-ver-detalle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tr = e.target.closest('tr');
            document.getElementById('det-id').textContent        = tr.dataset.id;
            document.getElementById('det-empleado').textContent  = tr.dataset.empleado || '';
            document.getElementById('det-tipo').textContent      = tr.dataset.tipo || '';
            document.getElementById('det-dias').textContent      = tr.dataset.dias || '-';
            document.getElementById('det-inicio').textContent    = tr.dataset.inicio || '';
            document.getElementById('det-fin').textContent       = tr.dataset.fin || '';

            const est  = (tr.dataset.estado || 'pendiente').toLowerCase();
            const badge = document.getElementById('det-estado');
            badge.className = 'badge';
            if (est === 'aprobada')      badge.classList.add('bg-success');
            else if (est === 'rechazada') badge.classList.add('bg-danger');
            else                          badge.classList.add('bg-warning','text-dark');
            badge.textContent = est.charAt(0).toUpperCase() + est.slice(1);

            document.getElementById('det-razon').textContent = tr.dataset.razon || '';
        });
    });

    // Pasar id al modal de Atender
    document.querySelectorAll('.btn-atender').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tr = e.target.closest('tr');
            document.getElementById('att-id').value       = tr.dataset.id;
            document.getElementById('att-id-label').textContent = `#${tr.dataset.id}`;
        });
    });

    // Botón limpiar filtros (ejemplo simple)
    document.getElementById('btn-limpiar')?.addEventListener('click', () => {
        document.getElementById('filtro-q').value      = '';
        document.getElementById('filtro-estado').value = '';
        document.getElementById('filtro-tipo').value   = '';
    });

    // ====== TABS VACACIONES ======
    const tabDisponibles = document.getElementById('tab-disponibles');
    const tabProceso     = document.getElementById('tab-proceso');
    const tabCompletados = document.getElementById('tab-completados');

    const contDisp  = document.getElementById('contenedor-disponibles');
    const contProc  = document.getElementById('contenedor-proceso');
    const contComp  = document.getElementById('contenedor-completados');

    // Si no existen estos elementos, es otra vista: salimos
    if (!tabDisponibles || !tabProceso || !tabCompletados ||
        !contDisp || !contProc || !contComp) {
        return;
    }

    function activate(tab){
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
    }

    tabDisponibles.onclick = () => {
        activate(tabDisponibles);
        contDisp.style.display = '';
        contProc.style.display = 'none';
        contComp.style.display = 'none';
    };

    tabProceso.onclick = () => {
        activate(tabProceso);
        contDisp.style.display = 'none';
        contProc.style.display = '';
        contComp.style.display = 'none';
    };

    tabCompletados.onclick = () => {
        activate(tabCompletados);
        contDisp.style.display = 'none';
        contProc.style.display = 'none';
        contComp.style.display = '';
    };

    // ====== Buscador (solamente en Disponibles) ======
    const search = document.getElementById('vacSearch');
    const items  = document.querySelectorAll('#list-disponibles .form-item');

    search?.addEventListener('input', e => {
        const q = e.target.value.toLowerCase();
        items.forEach(it => {
            const name = it.querySelector('.form-name')?.innerText.toLowerCase() || '';
            it.style.display = name.includes(q) ? '' : 'none';
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
const form = document.getElementById('form-filtros');
const est  = document.getElementById('filtro-estado');
const tipo = document.getElementById('filtro-tipo');

est?.addEventListener('change', () => form.submit());
tipo?.addEventListener('change', () => form.submit());
});

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('dj-messages');
  if (!container || !window.Swal) return;

  const nodes = container.querySelectorAll('.dj-message');
  nodes.forEach(node => {
    const level = (node.dataset.level || '').toLowerCase();
    const text  = node.textContent.trim();

    let icon  = 'info';
    let title = 'Mensaje';

    if (level.includes('error')) {
      icon = 'error';
      title = 'Error';
    } else if (level.includes('success')) {
      icon = 'success';
      title = 'Éxito';
    } else if (level.includes('warning')) {
      icon = 'warning';
      title = 'Aviso';
    }

    Swal.fire({
      title: title,
      text: text,
      icon: icon,
      confirmButtonText: 'Aceptar'
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  // Usar los mensajes de Django que ya están en base.html (.messages .alert)
  if (!window.Swal) return;

  const alerts = document.querySelectorAll('.messages .alert');
  alerts.forEach(alert => {
    const text = alert.textContent.trim();
    if (!text) return;

    const classes = alert.className;
    let icon  = 'info';
    let title = 'Mensaje';

    if (classes.includes('alert-success')) {
      icon = 'success';
      title = 'Éxito';
    } else if (classes.includes('alert-danger') || classes.includes('alert-error')) {
      icon = 'error';
      title = 'Error';
    } else if (classes.includes('alert-warning')) {
      icon = 'warning';
      title = 'Aviso';
    }

    // Mostrar SweetAlert
    Swal.fire({
      title: title,
      text: text,
      icon: icon,
      confirmButtonText: 'Aceptar'
    });

    // Opcional: ocultar el alert de Bootstrap para que no se vea doble
    alert.style.display = 'none';
  });
});
