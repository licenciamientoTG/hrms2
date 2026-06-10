// ── Utilidad global ──────────────────────────────────────────────────────────

function getCsrf() {
  return document.cookie.split(';').map(function(c) { return c.trim(); })
    .find(function(c) { return c.startsWith('csrftoken='); })?.split('=')[1] || '';
}

// ── Totales por empleado (admin / zona) ──────────────────────────────────────

function actualizarTotalTipo(empId, tipo) {
  var cell = document.getElementById('total-' + empId + '-' + tipo);
  if (!cell) return;
  var count = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="' + tipo + '"]:checked').length;
  if (tipo === 'Diesel') {
    cell.textContent = '$' + (count * 50);
  } else if (tipo === 'Encargado') {
    cell.textContent = '$' + (count > 0 ? 200 + (count - 1) * 100 : 0);
  }
  actualizarGranTotalEmp(empId);
}

function actualizarGranTotalEmp(empId) {
  var granTotalCell = document.getElementById('gran-total-emp-' + empId);
  if (!granTotalCell) return;
  var dieselCount = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Diesel"]:checked').length;
  var encargadoCount = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Encargado"]:checked').length;
  var total = (dieselCount * 50) + (encargadoCount > 0 ? 200 + (encargadoCount - 1) * 100 : 0);
  granTotalCell.textContent = '$' + total;
}

// ── Construye e inyecta la tabla semanal de un empleado ──────────────────────

function buildEmpTable(empId) {
  var container = document.getElementById('emp-detail-' + empId);
  if (!container || container.dataset.built === '1') return;
  container.dataset.built = '1';

  var html = '<div class="table-responsive"><table class="table table-bordered align-middle incentives-week-table mb-0">';
  html += '<thead><tr><th style="min-width:120px;">INCENTIVO</th>';
  DIAS.forEach(function(dia) {
    html += '<th class="text-center' + (dia.esHoy ? ' day-today' : '') + '" style="min-width:68px;">';
    html += '<div class="day-name">' + dia.nombre + '</div>';
    html += '<div class="day-date">' + dia.display + '</div>';
    html += '</th>';
  });
  html += '<th style="min-width:130px;">COMENTARIOS</th>';
  html += '<th class="text-center" style="min-width:80px;">TOTAL</th>';
  html += '</tr></thead><tbody>';

  TIPOS.forEach(function(tipo) {
    html += '<tr><td class="fw-semibold" style="font-size:13px;">' + tipo + '</td>';
    DIAS.forEach(function(dia) {
      html += '<td class="text-center' + (dia.esHoy ? ' day-today' : '') + ' incentivo-cell-zona"'
            + ' data-emp="' + empId + '" data-tipo="' + tipo + '" data-fecha="' + dia.fecha + '">';
      html += '<input type="checkbox" class="incentivo-check form-check-input"'
            + ' data-emp="' + empId + '" data-tipo="' + tipo + '" data-fecha="' + dia.fecha + '"'
            + (PERIODO_CERRADO ? ' disabled' : '')
            + ' onclick="event.stopPropagation()">';
      html += '</td>';
    });
    html += '<td onclick="event.stopPropagation()">'
          + '<textarea class="comentario-semana form-control form-control-sm"'
          + ' data-emp="' + empId + '" data-tipo="' + tipo + '"'
          + ' rows="2" placeholder="Comentario…" style="font-size:12px;resize:none;"'
          + (PERIODO_CERRADO ? ' readonly' : '') + '></textarea>'
          + '</td>';
    if (tipo === 'Diesel' || tipo === 'Encargado') {
      html += '<td class="text-center fw-semibold" id="total-' + empId + '-' + tipo + '">$0</td>';
    } else {
      html += '<td class="text-center text-muted">—</td>';
    }
    html += '</tr>';
  });

  html += '<tr class="table-light fw-bold"><td>TOTAL GENERAL</td>';
  DIAS.forEach(function() { html += '<td></td>'; });
  html += '<td></td><td class="text-center text-success" id="gran-total-emp-' + empId + '">$0</td></tr>';
  html += '</tbody></table></div>';
  container.innerHTML = html;

  if (!PERIODO_CERRADO) {
    container.querySelectorAll('.incentivo-check').forEach(function(cb) {
      cb.addEventListener('change', function() { onToggle(cb); });
    });
    container.querySelectorAll('.comentario-semana').forEach(function(ta) {
      ta.addEventListener('blur', function() { onComentario(ta); });
    });
    container.querySelectorAll('.incentivo-cell-zona').forEach(function(td) {
      td.style.cursor = 'pointer';
      td.addEventListener('click', function() {
        var cb = td.querySelector('.incentivo-check');
        if (cb) cb.click();
      });
    });
  }
}

// ── Carga datos del empleado vía AJAX ────────────────────────────────────────

function cargarSemana(empId) {
  fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;
      data.registros.forEach(function(reg) {
        var cb = document.querySelector(
          '.incentivo-check[data-emp="' + empId + '"][data-tipo="' + reg.tipo + '"][data-fecha="' + reg.fecha + '"]'
        );
        if (cb) cb.checked = true;
      });
      if (data.comentarios) {
        Object.keys(data.comentarios).forEach(function(tipo) {
          var ta = document.querySelector(
            '.comentario-semana[data-emp="' + empId + '"][data-tipo="' + tipo + '"]'
          );
          if (ta) ta.value = data.comentarios[tipo] || '';
        });
      }
      TIPOS.forEach(function(tipo) { actualizarTotalTipo(empId, tipo); });
    });
}

// ── Toggle checkbox ──────────────────────────────────────────────────────────

function onToggle(cb) {
  var empId = cb.dataset.emp;
  var tipo  = cb.dataset.tipo;

  if (tipo === 'Diesel' && cb.checked) {
    var dieselMarcados = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Diesel"]:checked').length;
    if (dieselMarcados > 6) {
      cb.checked = false;
      Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Diesel por semana (tope $300)', confirmButtonColor: '#0d6efd' });
      return;
    }
  }

  if (tipo === 'Encargado' && cb.checked) {
    var encargadoMarcados = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Encargado"]:checked').length;
    if (encargadoMarcados > 6) {
      cb.checked = false;
      Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Encargado por semana (tope $700)', confirmButtonColor: '#0d6efd' });
      return;
    }
  }

  var cbRef = cb;
  fetch('/incentives/toggle/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    body: JSON.stringify({ emp: empId, tipo: tipo, fecha: cb.dataset.fecha }),
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (!data.ok) {
      cbRef.checked = !cbRef.checked;
      if (data.max_diesel) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Diesel por semana (tope $300)', confirmButtonColor: '#0d6efd' });
      if (data.max_encargado) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Encargado por semana (tope $700)', confirmButtonColor: '#0d6efd' });
    } else {
      actualizarBadge(empId);
      actualizarTotalTipo(empId, tipo);
    }
  })
  .catch(function() { cbRef.checked = !cbRef.checked; });
}

// ── Guardar comentario ───────────────────────────────────────────────────────

function onComentario(ta) {
  var empId = ta.dataset.emp;
  if (!empId) return;
  fetch('/incentives/comentario/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    body: JSON.stringify({ emp: empId, tipo: ta.dataset.tipo, week_start: SEMANA_INICIO, comentario: ta.value }),
  });
}

// ── Actualiza badge de conteo ────────────────────────────────────────────────

function actualizarBadge(empId) {
  var total = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"]:checked').length;
  var empRow = document.querySelector('.zona-emp-row[data-emp-id="' + empId + '"]');
  if (!empRow) return;
  var badge = empRow.querySelector('.zona-emp-badge');
  if (!badge) return;
  badge.className = total > 0 ? 'badge bg-primary zona-emp-badge' : 'badge bg-secondary zona-emp-badge';
  badge.textContent = total > 0 ? total : 'Sin registro';
}

// ── Totales gerente (una sola tabla, sin empId) ──────────────────────────────

function actualizarTotal(tipo) {
  var cell = document.querySelector('.total-col[data-tipo="' + tipo + '"]');
  if (!cell) return;
  var count = document.querySelectorAll('.incentivo-check[data-tipo="' + tipo + '"]:checked').length;
  if (tipo === 'Diesel') {
    cell.textContent = '$' + (count * 50);
  } else if (tipo === 'Encargado') {
    cell.textContent = '$' + (count > 0 ? 200 + (count - 1) * 100 : 0);
  }
  actualizarGranTotal();
}

function actualizarGranTotal() {
  var granTotalCell = document.getElementById('gran-total-semana');
  if (!granTotalCell) return;
  var dieselCount = document.querySelectorAll('.incentivo-check[data-tipo="Diesel"]:checked').length;
  var encargadoCount = document.querySelectorAll('.incentivo-check[data-tipo="Encargado"]:checked').length;
  var total = (dieselCount * 50) + (encargadoCount > 0 ? 200 + (encargadoCount - 1) * 100 : 0);
  granTotalCell.textContent = '$' + total;
}

function cargarSemanaManager(empId) {
  if (!empId) return;
  fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;
      document.querySelectorAll('.incentivo-check').forEach(function(cb) { cb.checked = false; });
      document.querySelectorAll('.comentario-semana').forEach(function(ta) { ta.value = ''; });
      data.registros.forEach(function(reg) {
        var cb = document.querySelector(
          '.incentivo-check[data-tipo="' + reg.tipo + '"][data-fecha="' + reg.fecha + '"]'
        );
        if (cb) cb.checked = true;
      });
      if (data.comentarios) {
        Object.keys(data.comentarios).forEach(function(tipo) {
          var ta = document.querySelector('.comentario-semana[data-tipo="' + tipo + '"]');
          if (ta) ta.value = data.comentarios[tipo] || '';
        });
      }
      ['Diesel', 'Encargado'].forEach(function(tipo) { actualizarTotal(tipo); });
    });
}

function actualizarTabla(select) {
  var opt       = select.options[select.selectedIndex];
  var empId     = opt.value;
  var iniciales = opt.dataset.iniciales || '';

  document.getElementById('emp-nombre').textContent = opt.dataset.nombre;
  document.getElementById('emp-puesto').textContent = opt.dataset.puesto;
  document.getElementById('emp-num').textContent = empId ? 'No. ' + opt.dataset.num : '';
  document.getElementById('emp-avatar-header').textContent = iniciales;

  document.querySelectorAll('.incentivo-check').forEach(function(el) {
    el.dataset.emp = empId;
    el.checked = false;
  });
  document.querySelectorAll('.comentario-semana').forEach(function(ta) {
    ta.dataset.emp = empId;
    ta.value = '';
  });
  document.querySelectorAll('.total-col').forEach(function(cell) { cell.textContent = '$0'; });
  var granTotalCell = document.getElementById('gran-total-semana');
  if (granTotalCell) granTotalCell.textContent = '$0';

  cargarSemanaManager(empId);
}

// ── DOM Ready ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {

  // Accordion de estaciones
  document.querySelectorAll('.station-row').forEach(function(row) {
    row.addEventListener('click', function() {
      var deptId = row.dataset.deptId;
      var detailRow = document.querySelector('.incentives-detail-row[data-dept-id="' + deptId + '"]');
      if (!detailRow) return;
      var isExpanded = row.classList.contains('expanded');
      document.querySelectorAll('.station-row.expanded').forEach(function(r) {
        if (r !== row) {
          r.classList.remove('expanded');
          var dr = document.querySelector('.incentives-detail-row[data-dept-id="' + r.dataset.deptId + '"]');
          if (dr) dr.classList.add('d-none');
        }
      });
      if (isExpanded) {
        row.classList.remove('expanded');
        detailRow.classList.add('d-none');
      } else {
        row.classList.add('expanded');
        detailRow.classList.remove('d-none');
      }
    });
  });

  // Accordion de empleados (zona / admin)
  document.querySelectorAll('.zona-emp-row').forEach(function(row) {
    row.addEventListener('click', function() {
      var empId = row.dataset.empId;
      var detailRow = document.querySelector('.zona-emp-detail-row[data-emp-id="' + empId + '"]');
      if (!detailRow) return;

      var isExpanded = row.classList.contains('zona-expanded');
      var icon = row.querySelector('.zona-emp-toggle');

      document.querySelectorAll('.zona-emp-row.zona-expanded').forEach(function(other) {
        if (other === row) return;
        other.classList.remove('zona-expanded');
        var otherIcon = other.querySelector('.zona-emp-toggle');
        if (otherIcon) otherIcon.style.transform = '';
        var otherDetail = document.querySelector('.zona-emp-detail-row[data-emp-id="' + other.dataset.empId + '"]');
        if (otherDetail) otherDetail.classList.add('d-none');
      });

      if (isExpanded) {
        row.classList.remove('zona-expanded');
        if (icon) icon.style.transform = '';
        detailRow.classList.add('d-none');
      } else {
        row.classList.add('zona-expanded');
        if (icon) icon.style.transform = 'rotate(90deg)';
        detailRow.classList.remove('d-none');

        if (row.dataset.loaded === '0') {
          row.dataset.loaded = '1';
          buildEmpTable(empId);
          cargarSemana(empId);
        }
      }
    });
  });

  // Filtro de búsqueda en la tabla de estaciones
  var searchInput = document.getElementById('incentives-search');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      var terms = this.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      document.querySelectorAll('.incentives-table tbody .station-row').forEach(function(row) {
        var deptId = row.dataset.deptId;
        var detailRow = document.querySelector('.incentives-detail-row[data-dept-id="' + deptId + '"]');
        var text = row.innerText.toLowerCase();
        var match = terms.length === 0 || terms.every(function(term) { return text.includes(term); });
        row.style.display = match ? '' : 'none';
        if (detailRow) detailRow.style.display = match ? '' : 'none';
      });
    });
  }

  // Cerrar estación
  document.querySelectorAll('.btn-close-station').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      var tr = btn.closest('tr');
      var station = tr ? tr.querySelector('td').innerText.trim() : 'esta estación';
      if (window.Swal) {
        Swal.fire({
          title: '¿Cerrar ' + station + '?',
          text: 'Confirma que deseas cerrar la estación para el periodo seleccionado.',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: 'Sí, cerrar',
          cancelButtonText: 'Cancelar',
        }).then(function(result) {
          if (result.isConfirmed) {
            Swal.fire('Cerrada', station + ' ha sido cerrada. (simulado)', 'success');
          }
        });
      } else {
        alert('Cerrar ' + station);
      }
    });
  });

  // Selector de colaborador (gerente)
  var selector = document.getElementById('selector-colaborador');
  if (selector) {
    actualizarTabla(selector);
    selector.addEventListener('change', function() { actualizarTabla(this); });
  }

  // Checkboxes gerente
  if (!window.PERIODO_CERRADO) {
    document.querySelectorAll('.incentivo-check').forEach(function(cb) {
      cb.addEventListener('change', function() {
        var empId = this.dataset.emp;
        var tipo  = this.dataset.tipo;
        var fecha = this.dataset.fecha;
        if (!empId) return;

        if (tipo === 'Diesel' && this.checked) {
          var dieselMarcados = document.querySelectorAll('.incentivo-check[data-tipo="Diesel"]:checked').length;
          if (dieselMarcados > 6) {
            this.checked = false;
            Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Diesel por semana (tope $300)', confirmButtonColor: '#0d6efd' });
            return;
          }
        }

        if (tipo === 'Encargado' && this.checked) {
          var encargadoMarcados = document.querySelectorAll('.incentivo-check[data-tipo="Encargado"]:checked').length;
          if (encargadoMarcados > 6) {
            this.checked = false;
            Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Encargado por semana (tope $700)', confirmButtonColor: '#0d6efd' });
            return;
          }
        }

        var cbRef = this;
        fetch('/incentives/toggle/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          body: JSON.stringify({ emp: empId, tipo: tipo, fecha: fecha }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (!data.ok) {
            cbRef.checked = !cbRef.checked;
            if (data.max_diesel) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Diesel por semana (tope $300)', confirmButtonColor: '#0d6efd' });
            if (data.max_encargado) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo 6 días de Encargado por semana (tope $700)', confirmButtonColor: '#0d6efd' });
          } else {
            actualizarTotal(tipo);
          }
        })
        .catch(function() { cbRef.checked = !cbRef.checked; });
      });
    });

    document.querySelectorAll('.comentario-semana').forEach(function(ta) {
      ta.addEventListener('blur', function() {
        var empId = this.dataset.emp;
        var tipo  = this.dataset.tipo;
        if (!empId) return;
        fetch('/incentives/comentario/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          body: JSON.stringify({ emp: empId, tipo: tipo, week_start: SEMANA_INICIO, comentario: this.value }),
        });
      });
    });
  }

  // Cerrar / reabrir periodo
  var btnClosePeriod = document.getElementById('btn-close-period');
  if (btnClosePeriod) {
    btnClosePeriod.addEventListener('click', function() {
      var cerrado = window.PERIODO_CERRADO;
      var accion  = cerrado ? 'reabrir' : 'cerrar';
      var mensaje = cerrado ? 'Se permitirá la edición nuevamente.' : 'Nadie podrá modificar incentivos hasta que lo reabras.';
      Swal.fire({
        title: '¿Deseas ' + accion + ' la semana?',
        text: mensaje,
        icon: cerrado ? 'question' : 'warning',
        showCancelButton: true,
        confirmButtonText: accion.charAt(0).toUpperCase() + accion.slice(1),
        cancelButtonText: 'Cancelar',
        confirmButtonColor: cerrado ? '#28a745' : '#dc3545',
      }).then(function(result) {
        if (!result.isConfirmed) return;
        fetch('/incentives/cerrar-semana/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          body: JSON.stringify({ week_start: window.SEMANA_INICIO }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (!data.ok) { Swal.fire('Error', data.error || 'desconocido', 'error'); return; }
          window.location.reload();
        })
        .catch(function() { Swal.fire('Error', 'Error de conexión', 'error'); });
      });
    });
  }

});
