document.addEventListener('DOMContentLoaded', function () {
  // Toggle de detalle de incentivos al hacer clic en la fila de estación
  document.querySelectorAll('.station-row').forEach(function (row) {
    row.addEventListener('click', function () {
      const deptId = row.dataset.deptId;
      const detailRow = document.querySelector(`.incentives-detail-row[data-dept-id="${deptId}"]`);
      if (!detailRow) return;
      const isExpanded = row.classList.contains('expanded');
      // Cerrar todas las demás filas abiertas
      document.querySelectorAll('.station-row.expanded').forEach(function (r) {
        if (r !== row) {
          r.classList.remove('expanded');
          const id = r.dataset.deptId;
          const dr = document.querySelector(`.incentives-detail-row[data-dept-id="${id}"]`);
          if (dr) dr.classList.add('d-none');
        }
      });
      // Toggle la fila actual
      if (isExpanded) {
        row.classList.remove('expanded');
        detailRow.classList.add('d-none');
      } else {
        row.classList.add('expanded');
        detailRow.classList.remove('d-none');
      }
    });
  });

  // Filtro de búsqueda en la tabla de estaciones
  const searchInput = document.getElementById('incentives-search');
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      const terms = this.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      document.querySelectorAll('.incentives-table tbody .station-row').forEach(row => {
        const deptId = row.dataset.deptId;
        const detailRow = document.querySelector(`.incentives-detail-row[data-dept-id="${deptId}"]`);
        const text = row.innerText.toLowerCase();
        const match = terms.length === 0 || terms.every(term => text.includes(term));
        row.style.display = match ? '' : 'none';
        if (detailRow) detailRow.style.display = match ? '' : 'none';
      });
    });
  }


  // Handler for closing a station
  document.querySelectorAll('.btn-close-station').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const tr = btn.closest('tr');
      const station = tr ? tr.querySelector('td').innerText.trim() : 'esta estación';
      if (window.Swal) {
        Swal.fire({
          title: `Cerrar ${station}?`,
          text: 'Confirma que deseas cerrar la estación para el periodo seleccionado.',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: 'Sí, cerrar',
          cancelButtonText: 'Cancelar'
        }).then(result => {
          if (result.isConfirmed) {
            Swal.fire('Cerrada', `${station} ha sido cerrada. (simulado)`, 'success');
          }
        });
      } else {
        alert('Cerrar ' + station);
      }
    });
  });

  // Handler for close period button
  const btnClosePeriod = document.getElementById('btn-close-period');
  if (btnClosePeriod) {
    btnClosePeriod.addEventListener('click', function () {
      if (window.Swal) {
        Swal.fire({
          title: 'Realizar cierre definitivo?',
          text: 'Esta acción cerrará el periodo para todas las estaciones. ¿Deseas continuar?',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: 'Sí, cerrar periodo',
          cancelButtonText: 'Cancelar'
        }).then(result => {
          if (result.isConfirmed) {
            Swal.fire('Periodo cerrado', 'El periodo ha sido cerrado. (simulado)', 'success');
          }
        });
      } else {
        if (confirm('Cerrar periodo?')) alert('Periodo cerrado (simulado)');
      }
    });
  }
});
