
// Hook mínimo para poblar el modal de detalle desde la fila clicada
document.querySelectorAll('.btn-ver-detalle').forEach(btn => {
    btn.addEventListener('click', (e) => {
    const tr = e.target.closest('tr');
    document.getElementById('det-id').textContent = tr.dataset.id;
    document.getElementById('det-empleado').textContent = tr.dataset.empleado || '';
    document.getElementById('det-tipo').textContent = tr.dataset.tipo || '';
    document.getElementById('det-dias').textContent = tr.dataset.dias || '-';
    document.getElementById('det-inicio').textContent = tr.dataset.inicio || '';
    document.getElementById('det-fin').textContent = tr.dataset.fin || '';
    const est = (tr.dataset.estado || 'pendiente').toLowerCase();
    const badge = document.getElementById('det-estado');
    badge.className = 'badge';
    if (est === 'aprobada') badge.classList.add('bg-success');
    else if (est === 'rechazada') badge.classList.add('bg-danger');
    else badge.classList.add('bg-warning','text-dark');
    badge.textContent = est.charAt(0).toUpperCase()+est.slice(1);
    document.getElementById('det-razon').textContent = tr.dataset.razon || '';
    });
});

// Pasar id al modal de Atender
document.querySelectorAll('.btn-atender').forEach(btn => {
    btn.addEventListener('click', (e) => {
    const tr = e.target.closest('tr');
    document.getElementById('att-id').value = tr.dataset.id;
    document.getElementById('att-id-label').textContent = `#${tr.dataset.id}`;
    });
});

// Botón limpiar filtros (ejemplo simple)
document.getElementById('btn-limpiar')?.addEventListener('click', () => {
    document.getElementById('filtro-q').value = '';
    document.getElementById('filtro-estado').value = '';
    document.getElementById('filtro-tipo').value = '';
    // Aquí llamarías a la recarga o filtrado vía JS/servidor
});