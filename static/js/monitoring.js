// ===== Tooltips de los cuadritos de uso semanal =====
if (window.bootstrap) {
  document.querySelectorAll('.usage-week .day').forEach(el => {
    if (!bootstrap.Tooltip.getInstance(el)) new bootstrap.Tooltip(el);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Puedes usar #monitoring-search/#monitoring-clear (recomendado)
  // o seguir usando name="q" si aún no pusiste los IDs.
  const input   = document.getElementById('monitoring-search') || document.querySelector('input[name="q"]');
  const clearBn = document.getElementById('monitoring-clear');
  const table   = document.getElementById('admin-monitoring-table');
  if (!input || !table) return;

  // Evita submit del form al presionar Enter
  input.closest('form')?.addEventListener('submit', e => e.preventDefault());

  const rows = Array.from(table.querySelectorAll('tbody tr'));
  // fila "Sin resultados"
  let emptyRow = table.querySelector('tbody .js-empty-row');
  if (!emptyRow) {
    emptyRow = document.createElement('tr');
    emptyRow.className = 'js-empty-row d-none';
    emptyRow.innerHTML = `<td colspan="6" class="text-center text-muted">Sin resultados.</td>`;
    table.querySelector('tbody').appendChild(emptyRow);
  }

  const applyFilter = () => {
    const term = (input.value || '').trim().toLowerCase();

    // Actualiza la URL (sin recargar) para poder compartir/boton "atrás"
    const url = new URL(window.location.href);
    if (term) { url.searchParams.set('q', term); url.searchParams.delete('page'); }
    else { url.searchParams.delete('q'); }
    window.history.replaceState({}, '', url);

    // Mostrar/ocultar botón "Limpiar"
    if (clearBn) clearBn.classList.toggle('d-none', !term);

    // Filtrar filas por Nombre, Usuario o Lugar
    let visible = 0;
    rows.forEach(tr => {
      const name  = (tr.children[0]?.textContent || '').toLowerCase();
      const user  = (tr.children[1]?.textContent || '').toLowerCase();
      const place = (tr.children[2]?.textContent || '').toLowerCase();
      const show  = !term || name.includes(term) || user.includes(term) || place.includes(term);
      tr.classList.toggle('d-none', !show);
      if (show) visible++;
    });

    emptyRow.classList.toggle('d-none', visible !== 0);

    // Reaplicar tooltips a elementos visibles
    if (window.bootstrap) {
      document.querySelectorAll('.usage-week .day').forEach(el => {
        if (!bootstrap.Tooltip.getInstance(el)) new bootstrap.Tooltip(el);
      });
    }
  };

  // Debounce para escribir cómodo
  let t = null;
  input.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(applyFilter, 120);
  });

  // Botón "Limpiar"
  if (clearBn) {
    clearBn.addEventListener('click', () => {
      input.value = '';
      input.focus();
      applyFilter();
    });
  }

  // Aplica si llegas con ?q= en la URL
  applyFilter();
});
