function toggle360Option() {
    const isCuali = document.getElementById('tipoCuali').checked;
    const container360 = document.getElementById('container360');
    const check360 = document.getElementById('check360');

    if (isCuali) {
        // Usamos jQuery para una animación suave si está disponible, si no, CSS display
        if (typeof $ !== 'undefined') {
            $(container360).slideDown(200);
        } else {
            container360.style.display = 'block';
        }
    } else {
        if (typeof $ !== 'undefined') {
            $(container360).slideUp(200);
        } else {
            container360.style.display = 'none';
        }
        check360.checked = false; 
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('initEvalModal');
    
    modal.addEventListener('show.bs.modal', function () {
        const today = new Date();
        const currentYear = today.getFullYear();
        
        // Generar nombre automático: Evaluación [Mes] [Año]
        const monthName = today.toLocaleString('es-ES', { month: 'long' });
        const capitalizedMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1);
        const evalName = `Evaluación ${capitalizedMonth} ${currentYear}`;
        
        document.getElementById('autoEvalName').value = evalName;
        document.getElementById('autoFiscalYear').value = currentYear;
        
        // Asegurarnos que el estado del 360 sea correcto al abrir
        toggle360Option();
    });
});

// ── Filtros de departamentos (vista admin) ──
let filtroActual = 'all';

function setFiltro(f) {
    filtroActual = f;
    document.querySelectorAll('[id^="f-"]').forEach(b => b.classList.remove('active'));
    document.getElementById('f-' + f).classList.add('active');
    filtrarDepts();
}

function filtrarDepts() {
    const searchEl = document.getElementById('deptSearch');
    const q = searchEl ? searchEl.value.toLowerCase() : '';
    document.querySelectorAll('.dept-col').forEach(col => {
        const nombre = col.dataset.dept;
        const done = col.dataset.done;
        const matchQ = nombre.includes(q);
        const matchF = filtroActual === 'all'
            || (filtroActual === 'done' && done === '1')
            || (filtroActual === 'pend' && done === '0');
        col.style.display = matchQ && matchF ? '' : 'none';
    });
}

// ── Excluir apto de la lista ──
document.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-excluir-apto');
    if (!btn) return;

    const url = btn.dataset.url;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            btn.closest('tr').remove();
            const count = document.querySelectorAll('#aptosTableBody tr').length;
            const badge = document.querySelector('#aptosModal .badge.bg-success');
            if (badge) badge.textContent = count + ' encontrados';
            const countInit = document.querySelector('#initEvalModal strong[data-aptos-count]');
            if (countInit) countInit.textContent = count;
        }
    });
});

// ── Toggle puesto evaluable ──
document.addEventListener('change', function (e) {
    const chk = e.target.closest('.toggle-puesto');
    if (!chk) return;

    const url = chk.dataset.url;
    const checked = chk.checked;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) {
            chk.checked = !checked;
        } else {
            chk.closest('.puesto-item').style.borderLeftColor = checked ? '#0d6efd' : 'transparent';
            const badge = document.querySelector('#aptosModal .badge.bg-success');
            if (badge) badge.textContent = data.aptos_count + ' encontrados';
            const countInit = document.querySelector('#initEvalModal strong[data-aptos-count]');
            if (countInit) countInit.textContent = data.aptos_count;
        }
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const closeForms = document.querySelectorAll('.js-confirm-close');
    
    closeForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            Swal.fire({
                title: '¿Finalizar ciclo de evaluación?',
                text: "Esta acción cerrará todas las evaluaciones pendientes y moverá el ciclo al historial.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, finalizar ahora',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });
});