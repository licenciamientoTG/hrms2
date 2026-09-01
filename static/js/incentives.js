// ── Utilidad global ──────────────────────────────────────────────────────────

function getCsrf() {
  return document.cookie.split(';').map(function(c) { return c.trim(); })
    .find(function(c) { return c.startsWith('csrftoken='); })?.split('=')[1] || '';
}

// Valores de configuración inyectados por el template (con fallback a los defaults)
var _CFG_DIESEL           = function() { return typeof CFG_DIESEL_POR_DIA          !== 'undefined' ? CFG_DIESEL_POR_DIA          : 50;  };
var _CFG_DIESEL_MAX       = function() { return typeof CFG_DIESEL_MAX_DIAS         !== 'undefined' ? CFG_DIESEL_MAX_DIAS         : 6;   };
var _CFG_ENC1             = function() { return typeof CFG_ENC_PRIMER_DIA          !== 'undefined' ? CFG_ENC_PRIMER_DIA          : 200; };
var _CFG_ENCINC           = function() { return typeof CFG_ENC_INCREMENTO          !== 'undefined' ? CFG_ENC_INCREMENTO          : 100; };
var _CFG_ENC_MAX          = function() { return typeof CFG_ENC_MAX_DIAS            !== 'undefined' ? CFG_ENC_MAX_DIAS            : 6;   };
var _CFG_MISTERY_EVALUADO = function() { return typeof CFG_MISTERY_MONTO_EVALUADO  !== 'undefined' ? CFG_MISTERY_MONTO_EVALUADO  : 500; };

function _calcDiesel(count)    { return count * _CFG_DIESEL(); }
function _calcEncargado(count) { return count > 0 ? _CFG_ENC1() + (count - 1) * _CFG_ENCINC() : 0; }
function _topeEncargado()      { return _CFG_ENC1() + (_CFG_ENC_MAX() - 1) * _CFG_ENCINC(); }
function _topeDiesel()         { return _CFG_DIESEL() * _CFG_DIESEL_MAX(); }

// ── Totales por empleado (admin / zona) ──────────────────────────────────────

function actualizarTotalTipo(empId, tipo) {
  var cell = document.getElementById('total-' + empId + '-' + tipo);
  if (!cell) return;
  var count = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="' + tipo + '"]:checked').length;
  if (tipo === 'Diesel') {
    cell.textContent = '$' + _calcDiesel(count);
  } else if (tipo === 'Encargado') {
    cell.textContent = '$' + _calcEncargado(count);
  }
  actualizarGranTotalEmp(empId);
}

function actualizarGranTotalEmp(empId) {
  var granTotalCell = document.getElementById('gran-total-emp-' + empId);
  if (!granTotalCell) return;
  var dieselCount = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Diesel"]:checked').length;
  var encargadoCount = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Encargado"]:checked').length;
  var ventaCb = document.querySelector('.incentivo-check[data-emp="' + empId + '"][data-tipo="Venta"]:checked');
  var ventaMonto = ventaCb ? (parseInt(ventaCb.dataset.monto) || 0) : 0;
  var misteryCell = document.getElementById('total-' + empId + '-Mistery');
  var misteryMonto = 0;
  if (misteryCell && misteryCell.textContent.startsWith('$')) {
    misteryMonto = parseInt(misteryCell.textContent.slice(1)) || 0;
  }
  var total = _calcDiesel(dieselCount) + _calcEncargado(encargadoCount) + ventaMonto + misteryMonto;
  granTotalCell.textContent = '$' + total;
}

// ── Construye e inyecta la tabla semanal de un empleado ──────────────────────

function buildEmpTable(empId) {
  var container = document.getElementById('emp-detail-' + empId);
  if (!container || container.dataset.built === '1') return;
  container.dataset.built = '1';

  // ── Contexto: nombre de estación y colaborador ──
  var empRow      = document.querySelector('.zona-emp-row[data-emp-id="' + empId + '"]');
  var empNombre   = empRow ? (empRow.querySelectorAll('td')[1] || {}).innerText || '' : '';
  var empPuesto   = empRow ? (empRow.querySelectorAll('td')[2] || {}).innerText || '' : '';
  var detailParent = empRow ? empRow.closest('.incentives-detail-row') : null;
  var stationRow  = detailParent ? document.querySelector('.station-row[data-dept-id="' + detailParent.dataset.deptId + '"]') : null;
  var estNombre   = stationRow ? (stationRow.querySelectorAll('td')[1] || {}).innerText || '' : '';

  var contextoHtml = '';
  if (estNombre || empNombre) {
    contextoHtml = '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:14px 20px;margin-bottom:14px;background:#f0f6ff;border:1px solid #c7ddf9;border-radius:10px;font-size:18px;">'
      + (estNombre ? '<span style="background:#1e40af;color:#fff;border-radius:8px;padding:8px 18px;font-weight:700;"><i class="fas fa-gas-pump me-2"></i>' + estNombre + '</span>' : '')
      + (estNombre && empNombre ? '<i class="fas fa-chevron-right" style="color:#6b7280;font-size:15px;"></i>' : '')
      + (empNombre ? '<span style="background:#fff;border:1px solid #93c5fd;color:#1e40af;border-radius:8px;padding:8px 18px;font-weight:700;"><i class="fas fa-user me-2"></i>' + empNombre.trim() + '</span>' : '')
      + (empPuesto ? '<span style="color:#6b7280;font-size:15px;">· ' + empPuesto.trim() + '</span>' : '')
      + '</div>';
  }

  var html = contextoHtml + '<div class="table-responsive"><table class="table table-bordered align-middle incentives-week-table mb-0">';
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

  var tiposUsar = (typeof TIPOS_MANAGER !== 'undefined' && empRow && empRow.classList.contains('emp-manager-row'))
    ? TIPOS_MANAGER : TIPOS;
  tiposUsar.forEach(function(tipo) {
    html += '<tr><td class="fw-semibold" style="font-size:13px;">' + tipo + '</td>';
    if (tipo === 'Venta') {
      html += '<td colspan="' + DIAS.length + '" class="text-center py-2" id="venta-badge-emp-' + empId + '">';
      html += '<span class="text-muted" style="font-size:12px;"><i class="fas fa-circle-notch fa-spin me-1"></i>Verificando…</span>';
      html += '<input type="checkbox" class="incentivo-check d-none"'
            + ' data-emp="' + empId + '" data-tipo="Venta" data-fecha="' + SEMANA_INICIO + '"'
            + ' data-badge-id="venta-badge-emp-' + empId + '"'
            + ' disabled>';
      html += '</td>';
    } else if (tipo === 'Mistery') {
      html += '<td colspan="' + DIAS.length + '" class="text-center py-2" id="mistery-badge-emp-' + empId + '">';
      html += '<span class="text-muted" style="font-size:12px;"><i class="fas fa-circle-notch fa-spin me-1"></i>Verificando…</span>';
      html += '<input type="checkbox" class="incentivo-check d-none"'
            + ' data-emp="' + empId + '" data-tipo="Mistery" data-fecha="' + SEMANA_INICIO + '"'
            + ' disabled>';
      html += '</td>';
    } else if (tipo === 'ECV') {
      var indEcv = [
        { id: 'venta_gas',    icon: 'fa-gas-pump',       label: 'Venta Gasolina'       },
        { id: 'venta_diesel', icon: 'fa-oil-can',         label: 'Venta Di\u00e9sel'    },
        { id: 'mistery',      icon: 'fa-user-secret',     label: 'Mistery Shopper'      },
        { id: 'faltante',     icon: 'fa-balance-scale',   label: 'Faltante'             },
        { id: 'incidencia',   icon: 'fa-cut',             label: 'Incidencia en cortes' },
      ];
      html += '<td colspan="' + DIAS.length + '" class="py-2 px-3">';
      html += '<div class="d-flex flex-wrap gap-2 align-items-center">';
      indEcv.forEach(function(ind) {
        html += '<span class="ecv-indicador badge rounded-pill inactivo"'
              + ' id="ecv-ind-' + ind.id + '-' + empId + '" data-ind="' + ind.id + '"'
              + ' style="font-size:12px;padding:6px 12px;cursor:default;">'
              + '<i class="fas ' + ind.icon + ' me-1"></i>' + ind.label
              + '</span>';
      });
      html += '</div></td>';
    } else {
      DIAS.forEach(function(dia) {
        html += '<td class="text-center' + (dia.esHoy ? ' day-today' : '') + ' incentivo-cell-zona"'
              + ' data-emp="' + empId + '" data-tipo="' + tipo + '" data-fecha="' + dia.fecha + '">';
        html += '<input type="checkbox" class="incentivo-check form-check-input"'
              + ' data-emp="' + empId + '" data-tipo="' + tipo + '" data-fecha="' + dia.fecha + '"'
              + (PERIODO_CERRADO ? ' disabled' : '')
              + ' onclick="event.stopPropagation()">';
        html += '</td>';
      });
    }
    html += '<td onclick="event.stopPropagation()">'
          + '<textarea class="comentario-semana form-control form-control-sm"'
          + ' data-emp="' + empId + '" data-tipo="' + tipo + '"'
          + ' rows="2" placeholder="Comentario…" style="font-size:12px;resize:none;"'
          + (PERIODO_CERRADO ? ' readonly' : '') + '></textarea>'
          + '</td>';
    if (tipo === 'Diesel' || tipo === 'Encargado') {
      html += '<td class="text-center fw-semibold" id="total-' + empId + '-' + tipo + '">$0</td>';
    } else if (tipo === 'Venta') {
      html += '<td class="text-center fw-semibold text-muted" id="total-' + empId + '-Venta">—</td>';
    } else if (tipo === 'Mistery') {
      html += '<td class="text-center fw-semibold text-muted" id="total-' + empId + '-Mistery">—</td>';
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

// ── Actualiza el badge visual de Mistery para un empleado ────────────────────

function actualizarBadgeMistery(empId, ganado, monto) {
  var cell = document.getElementById('mistery-badge-emp-' + empId);
  if (!cell) return;
  var totalCell = document.getElementById('total-' + empId + '-Mistery');
  if (ganado) {
    var esEvaluado = monto && parseInt(monto) >= _CFG_MISTERY_EVALUADO();
    var etiqueta   = esEvaluado
      ? ' <span style="font-size:10px;background:#f59e0b;color:#fff;border-radius:3px;padding:1px 5px;margin-left:3px;vertical-align:middle;">EVALUADO</span>'
      : '';
    var bg    = esEvaluado ? '#fef3c7' : '#ede9fe';
    var color = esEvaluado ? '#92400e' : '#5b21b6';
    cell.innerHTML = '<span style="display:inline-block;background:' + bg + ';color:' + color + ';border-radius:6px;padding:4px 12px;font-size:12px;font-weight:600;">'
      + '<i class="fas fa-star me-1"></i>Ganó Mistery' + etiqueta + '</span>'
      + '<input type="checkbox" class="incentivo-check d-none"'
      + ' data-emp="' + empId + '" data-tipo="Mistery" data-fecha="' + SEMANA_INICIO + '" disabled checked>';
    if (totalCell) { totalCell.textContent = monto ? '$' + monto : '—'; totalCell.classList.remove('text-muted'); }
  } else {
    cell.innerHTML = '<span style="display:inline-block;background:#f3f4f6;color:#6b7280;border-radius:6px;padding:4px 12px;font-size:12px;">'
      + '<i class="fas fa-times-circle me-1"></i>Sin Mistery esta semana</span>'
      + '<input type="checkbox" class="incentivo-check d-none"'
      + ' data-emp="' + empId + '" data-tipo="Mistery" data-fecha="' + SEMANA_INICIO + '" disabled>';
    if (totalCell) { totalCell.textContent = '—'; totalCell.classList.add('text-muted'); }
  }
  actualizarGranTotalEmp(empId);
}

// ── Actualiza el badge visual del bono de Venta para un empleado ─────────────

function actualizarBadgeVenta(empId, ganado, monto) {
  var badgeId = 'venta-badge-emp-' + empId;
  var cell = document.getElementById(badgeId);
  var totalCell = document.getElementById('total-' + empId + '-Venta');
  if (!cell) return;
  if (ganado) {
    cell.innerHTML = '<span style="display:inline-block;background:#d1fae5;color:#065f46;border-radius:6px;padding:4px 12px;font-size:12px;font-weight:600;">'
      + '<i class="fas fa-check-circle me-1"></i>Bono ganado</span>'
      + '<input type="checkbox" class="incentivo-check d-none"'
      + ' data-emp="' + empId + '" data-tipo="Venta" data-fecha="' + SEMANA_INICIO + '"'
      + ' data-badge-id="' + badgeId + '" data-monto="' + (monto || 0) + '" disabled checked>';
    if (totalCell) { totalCell.textContent = monto ? '$' + monto : '—'; totalCell.classList.remove('text-muted'); }
  } else {
    cell.innerHTML = '<span style="display:inline-block;background:#f3f4f6;color:#6b7280;border-radius:6px;padding:4px 12px;font-size:12px;">'
      + '<i class="fas fa-times-circle me-1"></i>Sin bono esta semana</span>'
      + '<input type="checkbox" class="incentivo-check d-none"'
      + ' data-emp="' + empId + '" data-tipo="Venta" data-fecha="' + SEMANA_INICIO + '"'
      + ' data-badge-id="' + badgeId + '" data-monto="0" disabled>';
    if (totalCell) { totalCell.textContent = '—'; totalCell.classList.add('text-muted'); }
  }
  actualizarGranTotalEmp(empId);
}

// ── Carga datos del empleado vía AJAX ────────────────────────────────────────

function cargarSemana(empId) {
  fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;
      var tieneVenta = false;
      var ventaMonto = null;
      var tieneMistery = false;
      var misteryMonto = null;
      data.registros.forEach(function(reg) {
        if (reg.tipo === 'Venta') {
          tieneVenta = true;
          ventaMonto = reg.monto;
          return;
        }
        if (reg.tipo === 'Mistery') {
          tieneMistery = true;
          misteryMonto = reg.monto;
          return;
        }
        var cb = document.querySelector(
          '.incentivo-check[data-emp="' + empId + '"][data-tipo="' + reg.tipo + '"][data-fecha="' + reg.fecha + '"]'
        );
        if (cb) cb.checked = true;
      });
      actualizarBadgeVenta(empId, tieneVenta, ventaMonto);
      actualizarBadgeMistery(empId, tieneMistery, misteryMonto);
      _actualizarECVVentaEmp(empId);
      actualizarIndicadorECV('mistery', tieneMistery, empId);
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

function _doToggleFetch(cb, empId, tipo) {
  var cbRef = cb;
  var checkedState = cb.checked;
  fetch('/incentives/toggle/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    body: JSON.stringify({ emp: empId, tipo: tipo, fecha: cb.dataset.fecha }),
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (!data.ok) {
      cbRef.checked = !cbRef.checked;
      if (data.max_diesel) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_DIESEL_MAX() + ' días de Diesel por semana (tope $' + _topeDiesel() + ')', confirmButtonColor: '#0d6efd' });
      if (data.max_encargado) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_ENC_MAX() + ' días de Encargado por semana (tope $' + _topeEncargado() + ')', confirmButtonColor: '#0d6efd' });
    } else {
      actualizarBadge(empId);
      actualizarTotalTipo(empId, tipo);
      actualizarResumenGlobal(empId, tipo, checkedState);
    }
  })
  .catch(function() { cbRef.checked = !cbRef.checked; });
}

function onToggle(cb) {
  var empId = cb.dataset.emp;
  var tipo  = cb.dataset.tipo;

  if (tipo === 'Diesel' && cb.checked) {
    var dieselMarcados = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Diesel"]:checked').length;
    if (dieselMarcados > _CFG_DIESEL_MAX()) {
      cb.checked = false;
      Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_DIESEL_MAX() + ' días de Diesel por semana (tope $' + _topeDiesel() + ')', confirmButtonColor: '#0d6efd' });
      return;
    }
    if (dieselMarcados === 1) {
      Swal.fire({
        icon: 'info',
        title: 'Incentivo Diesel',
        html: 'El incentivo de Diesel <strong>solo aplica para el primer y segundo turno</strong>.',
        confirmButtonColor: '#0d6efd',
        confirmButtonText: 'Entendido',
      }).then(function() {
        _doToggleFetch(cb, empId, tipo);
      });
      return;
    }
  }

  if (tipo === 'Encargado' && cb.checked) {
    var encargadoMarcados = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Encargado"]:checked').length;
    if (encargadoMarcados > _CFG_ENC_MAX()) {
      cb.checked = false;
      Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_ENC_MAX() + ' días de Encargado por semana (tope $' + _topeEncargado() + ')', confirmButtonColor: '#0d6efd' });
      return;
    }
  }

  _doToggleFetch(cb, empId, tipo);
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

// ── Actualiza badge de conteo + punto verde de estación + resumen global ─────

function actualizarBadge(empId) {
  var total = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"]:checked').length;
  var empRow = document.querySelector('.zona-emp-row[data-emp-id="' + empId + '"]');
  if (!empRow) return;
  var badge = empRow.querySelector('.zona-emp-badge');
  if (!badge) return;
  badge.className = total > 0 ? 'badge bg-primary zona-emp-badge' : 'badge bg-secondary zona-emp-badge';
  badge.textContent = total > 0 ? total : 'Sin registro';

  actualizarPuntoVerdeEstacion(empRow);
}

function actualizarPuntoVerdeEstacion(empRow) {
  var detailRow = empRow.closest('.incentives-detail-row');
  if (!detailRow) return;
  var deptId = detailRow.dataset.deptId;
  var stationRow = document.querySelector('.station-row[data-dept-id="' + deptId + '"]');
  if (!stationRow) return;
  var capturaCell = stationRow.querySelector('td:last-child');
  if (!capturaCell) return;

  var badges = detailRow.querySelectorAll('.zona-emp-badge');
  var tieneCaptura = Array.from(badges).some(function(b) { return b.classList.contains('bg-primary'); });

  var dot = capturaCell.querySelector('span');
  if (tieneCaptura && !dot) {
    var newDot = document.createElement('span');
    newDot.title = 'Ya hay incentivos registrados esta semana';
    newDot.style.cssText = 'display:inline-block; width:10px; height:10px; background:#28a745; border-radius:50%;';
    capturaCell.appendChild(newDot);
  } else if (!tieneCaptura && dot) {
    dot.remove();
  }
}

function calcularDeltaPresupuesto(empId, tipo, checked) {
  if (tipo === 'Diesel') {
    return checked ? _CFG_DIESEL() : -_CFG_DIESEL();
  }
  if (tipo === 'Encargado') {
    var count = document.querySelectorAll('.incentivo-check[data-emp="' + empId + '"][data-tipo="Encargado"]:checked').length;
    if (checked) return count === 1 ? _CFG_ENC1() : _CFG_ENCINC();
    else         return count === 0 ? -_CFG_ENC1() : -_CFG_ENCINC();
  }
  return 0;
}

function actualizarResumenGlobal(empId, tipo, checked) {
  var valEl = document.getElementById('presupuesto-global-val');
  if (!valEl) return; // no es la vista admin

  var delta = calcularDeltaPresupuesto(empId, tipo, checked);
  window.PRESUPUESTO_GLOBAL = (window.PRESUPUESTO_GLOBAL || 0) + delta;
  valEl.textContent = '$' + window.PRESUPUESTO_GLOBAL;

  // Estaciones con captura: contar puntos verdes activos en el DOM
  var estaciones = document.querySelectorAll('.station-row td:last-child span').length;
  window.ESTACIONES_CON_CAPTURA = estaciones;

  var estEl = document.getElementById('estaciones-captura-val');
  if (estEl) {
    estEl.innerHTML = estaciones
      + ' <small class="text-muted" style="font-size:14px;">de '
      + (window.TOTAL_ESTACIONES || 0) + ' estaciones</small>';
  }

  var barEl = document.getElementById('progress-captura-bar');
  if (barEl && window.TOTAL_ESTACIONES > 0) {
    barEl.style.width = Math.round(estaciones / window.TOTAL_ESTACIONES * 100) + '%';
  }
}

// ── Totales gerente (una sola tabla, sin empId) ──────────────────────────────

function actualizarTotal(tipo) {
  var cell = document.querySelector('.total-col[data-tipo="' + tipo + '"]');
  if (!cell) return;
  var count = document.querySelectorAll('.incentivo-check[data-tipo="' + tipo + '"]:checked').length;
  if (tipo === 'Diesel') {
    cell.textContent = '$' + _calcDiesel(count);
  } else if (tipo === 'Encargado') {
    cell.textContent = '$' + _calcEncargado(count);
  }
  actualizarGranTotal();
}

function actualizarGranTotal() {
  var granTotalCell = document.getElementById('gran-total-semana');
  if (!granTotalCell) return;
  var dieselCount = document.querySelectorAll('.incentivo-check[data-tipo="Diesel"]:checked').length;
  var encargadoCount = document.querySelectorAll('.incentivo-check[data-tipo="Encargado"]:checked').length;
  var ventaMonto = window.VENTA_MONTO_MANAGER || 0;
  var misteryMonto = window.MISTERY_MONTO_MANAGER || 0;
  var total = _calcDiesel(dieselCount) + _calcEncargado(encargadoCount) + ventaMonto + misteryMonto;
  granTotalCell.textContent = '$' + total;
}

function actualizarBadgeMisteryManager(ganado, monto) {
  actualizarIndicadorECV('mistery', ganado ? true : false);
  var cell = document.getElementById('mistery-status-cell');
  var evaluadoRow = document.getElementById('mistery-evaluado-row');
  if (!cell) return;
  if (ganado) {
    var esEvaluado = monto && parseInt(monto) >= _CFG_MISTERY_EVALUADO();
    var etiqueta   = esEvaluado
      ? ' <span style="font-size:10px;background:#f59e0b;color:#fff;border-radius:3px;padding:1px 5px;margin-left:3px;vertical-align:middle;">EVALUADO</span>'
      : '';
    var bg    = esEvaluado ? '#fef3c7' : '#ede9fe';
    var color = esEvaluado ? '#92400e' : '#5b21b6';
    cell.innerHTML = '<span style="display:inline-block;background:' + bg + ';color:' + color + ';border-radius:6px;padding:5px 14px;font-size:13px;font-weight:600;">'
      + '<i class="fas fa-star me-1"></i>Ganó Mistery' + etiqueta + '</span>';
    if (evaluadoRow) {
      evaluadoRow.classList.remove('d-none');
      fetch('/incentives/mistery-evaluado/?semana=' + SEMANA_INICIO)
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (!d.ok) return;
          var sel = document.getElementById('mistery-evaluado-select');
          if (sel) sel.value = d.evaluado_emp_id || '';
        });
    }
  } else {
    cell.innerHTML = '<span style="display:inline-block;background:#f3f4f6;color:#6b7280;border-radius:6px;padding:5px 14px;font-size:13px;">'
      + '<i class="fas fa-times-circle me-1"></i>Sin Mistery esta semana</span>';
    if (evaluadoRow) evaluadoRow.classList.add('d-none');
    var totalCell = document.getElementById('mistery-total-cell');
    if (totalCell) { totalCell.textContent = '—'; totalCell.classList.add('text-muted'); }
  }
}

function cargarSemanaManager(empId) {
  if (!empId) return;
  fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;
      document.querySelectorAll('.incentivo-check').forEach(function(cb) { cb.checked = false; });
      document.querySelectorAll('.comentario-semana').forEach(function(ta) { ta.value = ''; });
      window.VENTA_MONTO_MANAGER = 0;
      window.MISTERY_MONTO_MANAGER = 0;
      var tieneVentaManager = false;
      var tieneMisteryManager = false;
      data.registros.forEach(function(reg) {
        if (reg.tipo === 'Venta') {
          tieneVentaManager = true;
          window.VENTA_MONTO_MANAGER = reg.monto || 0;
          return;
        }
        if (reg.tipo === 'Mistery') {
          tieneMisteryManager = true;
          window.MISTERY_MONTO_MANAGER = reg.monto || 0;
          return;
        }
        var cb = document.querySelector(
          '.incentivo-check[data-tipo="' + reg.tipo + '"][data-fecha="' + reg.fecha + '"]'
        );
        if (cb) cb.checked = true;
      });
      var ventaCell = document.getElementById('venta-status-cell');
      var ventaTotalCell = document.getElementById('venta-total-manager');
      if (ventaCell) {
        if (tieneVentaManager) {
          ventaCell.innerHTML = '<span style="display:inline-block;background:#d1fae5;color:#065f46;border-radius:6px;padding:5px 14px;font-size:13px;font-weight:600;">'
            + '<i class="fas fa-check-circle me-1"></i>Bono ganado</span>';
          if (ventaTotalCell) { ventaTotalCell.textContent = window.VENTA_MONTO_MANAGER ? '$' + window.VENTA_MONTO_MANAGER : '—'; ventaTotalCell.classList.remove('text-muted'); }
        } else {
          ventaCell.innerHTML = '<span style="display:inline-block;background:#f3f4f6;color:#6b7280;border-radius:6px;padding:5px 14px;font-size:13px;">'
            + '<i class="fas fa-times-circle me-1"></i>Sin bono esta semana</span>';
          if (ventaTotalCell) { ventaTotalCell.textContent = '—'; ventaTotalCell.classList.add('text-muted'); }
        }
      }
      actualizarBadgeMisteryManager(tieneMisteryManager, tieneMisteryManager ? window.MISTERY_MONTO_MANAGER : null);
      var misteryTotalCell = document.getElementById('mistery-total-cell');
      if (misteryTotalCell) {
        if (tieneMisteryManager && window.MISTERY_MONTO_MANAGER) {
          misteryTotalCell.textContent = '$' + window.MISTERY_MONTO_MANAGER;
          misteryTotalCell.classList.remove('text-muted');
        } else {
          misteryTotalCell.textContent = '—';
          misteryTotalCell.classList.add('text-muted');
        }
      }
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
  var vtm = document.getElementById('venta-total-manager');
  if (vtm) { vtm.textContent = '—'; vtm.classList.add('text-muted'); }
  var mtm = document.getElementById('mistery-total-cell');
  if (mtm) { mtm.textContent = '—'; mtm.classList.add('text-muted'); }
  var granTotalCell = document.getElementById('gran-total-semana');
  if (granTotalCell) granTotalCell.textContent = '$0';

  // Resetear badge de Mistery al cambiar de empleado
  var misteryCell = document.getElementById('mistery-status-cell');
  if (misteryCell) {
    misteryCell.innerHTML = '<span class="text-muted" style="font-size:12px;">'
      + '<i class="fas fa-circle-notch fa-spin me-1"></i>Verificando…</span>';
  }

  // Mostrar filas exclusivas de gerente/subgerente según el empleado seleccionado
  var esManager = opt.dataset.esManager === 'true';
  document.querySelectorAll('.tipo-manager-only').forEach(function(row) {
    if (esManager) {
      row.classList.remove('d-none');
    } else {
      row.classList.add('d-none');
    }
  });

  cargarSemanaManager(empId);
}

// ── Sincronización automática del bono de Venta ──────────────────────────────

// ── Actualiza un indicador ECV (activo/inactivo) ─────────────────────────────

function actualizarIndicadorECV(indId, activo, empId, pct) {
  // Manager: id="ecv-ind-venta-gas"  (sin empId)
  // Admin/zona: id="ecv-ind-venta_gas-123"  (con empId)
  var elId = empId ? ('ecv-ind-' + indId + '-' + empId) : ('ecv-ind-' + indId);
  var el = document.getElementById(elId);
  if (!el) return;
  el.classList.remove('activo', 'inactivo');
  el.style.background = '';
  el.style.color = '';
  el.style.boxShadow = '';
  if (activo === null || activo === undefined) return; // sin datos
  if (activo === true) {
    el.classList.add('activo');
  } else {
    // Rojo intenso → rojo claro según % alcanzado (0%=rojo oscuro, 99%=rosado claro)
    var ratio = (pct !== null && pct !== undefined) ? Math.min(Math.max(pct, 0), 99) / 99 : 0;
    // Lightness: 35% (rojo intenso) → 80% (rosado claro)
    var lightness = Math.round(35 + ratio * 45);
    var bg = 'hsl(354,' + (70 - ratio * 20) + '%,' + lightness + '%)';
    var textColor = lightness < 60 ? '#fff' : '#7a1a24';
    el.style.background = bg;
    el.style.color = textColor;
    el.style.boxShadow = '0 0 0 2px hsla(354,60%,' + lightness + '%,0.4)';
  }
}

function _pct(vs, ps) {
  return (ps && ps > 0) ? Math.round(vs / ps * 100) : null;
}

function _actualizarECVVentaEmp(empId) {
  if (!window._ecvEstaciones) return;
  var row = document.querySelector('.zona-emp-row[data-emp-id="' + empId + '"]');
  if (!row) return;
  var teamKey = row.dataset.teamKey;
  if (!teamKey) return;
  var est = window._ecvEstaciones[teamKey];
  if (!est) return;
  var pctGas = _pct(est.vs_gas, est.ps_gas);
  actualizarIndicadorECV('venta_gas', est.verde_gas, empId, pctGas);
  if (est.verde_diesel !== null && est.verde_diesel !== undefined) {
    var pctDiesel = _pct(est.vs_diesel, est.ps_diesel);
    actualizarIndicadorECV('venta_diesel', est.verde_diesel, empId, pctDiesel);
  }
}

function syncVentaSemana() {
  fetch('/incentives/sync-venta/?semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;

      // Vista gerente: actualizar indicadores ECV de venta_gas y venta_diesel
      if (typeof MANAGER_TEAM_KEY !== 'undefined' && MANAGER_TEAM_KEY) {
        var est = (data.estaciones || {})[MANAGER_TEAM_KEY];
        if (est) {
          actualizarIndicadorECV('venta-gas', est.verde_gas, null, _pct(est.vs_gas, est.ps_gas));
          if (typeof MANAGER_TIENE_DIESEL !== 'undefined' && MANAGER_TIENE_DIESEL) {
            actualizarIndicadorECV('venta-diesel', est.verde_diesel, null, _pct(est.vs_diesel, est.ps_diesel));
          }
        }
      }

      // Vista gerente: recargar el colaborador para que muestre el monto correcto
      var colSelVenta = document.getElementById('selector-colaborador');
      if (colSelVenta && colSelVenta.value) {
        cargarSemanaManager(colSelVenta.value);
      }

      // Vista admin/zona: guardar estaciones para uso en cargarSemana y actualizar expandidos
      window._ecvEstaciones = data.estaciones || {};
      document.querySelectorAll('.zona-emp-row.zona-expanded').forEach(function(row) {
        var empId = row.dataset.empId;
        if (!empId) return;
        _actualizarECVVentaEmp(empId);
        fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
          .then(function(r) { return r.json(); })
          .then(function(sd) {
            if (!sd.ok) return;
            var ventaReg = sd.registros.find(function(r) { return r.tipo === 'Venta'; });
            actualizarBadgeVenta(empId, !!ventaReg, ventaReg ? ventaReg.monto : null);
          });
      });
    })
    .catch(function() {
      var ventaCell = document.getElementById('venta-status-cell');
      if (ventaCell) {
        ventaCell.innerHTML = '<span class="text-muted" style="font-size:12px;">'
          + '<i class="fas fa-exclamation-triangle me-1"></i>Sin conexión a indicadores</span>';
      }
    });
}

// ── Sincronización automática de Mistery ─────────────────────────────────────

function syncMisterySemana() {
  fetch('/incentives/sync-mistery/?semana=' + SEMANA_INICIO)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) return;

      // Admin: mostrar/ocultar selector de evaluado por estación
      Object.keys(data.estaciones || {}).forEach(function(teamKey) {
        var est = data.estaciones[teamKey];
        var detailRow = document.querySelector('.incentives-detail-row[data-team-key="' + teamKey + '"]');
        if (!detailRow) return;
        var deptId = detailRow.dataset.deptId;
        var evaluadoDiv = document.getElementById('mistery-evaluado-admin-' + deptId);
        if (!evaluadoDiv) return;
        if (est.ganador) {
          evaluadoDiv.classList.remove('d-none');
          var sel = evaluadoDiv.querySelector('.mistery-evaluado-admin-select');
          if (sel) {
            fetch('/incentives/mistery-evaluado/?semana=' + SEMANA_INICIO + '&team_key=' + encodeURIComponent(teamKey))
              .then(function(r) { return r.json(); })
              .then(function(d) { if (d.ok && sel) sel.value = d.evaluado_emp_id || ''; });
          }
        } else {
          evaluadoDiv.classList.add('d-none');
        }
      });

      // Admin/zona: actualizar badge de empleados ya expandidos
      document.querySelectorAll('.zona-emp-row.zona-expanded').forEach(function(row) {
        var empId = row.dataset.empId;
        if (!empId) return;
        fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
          .then(function(r) { return r.json(); })
          .then(function(sd) {
            if (!sd.ok) return;
            var misteryReg = sd.registros.find(function(r) { return r.tipo === 'Mistery'; });
            actualizarBadgeMistery(empId, !!misteryReg, misteryReg ? misteryReg.monto : null);
          });
      });

      // Gerente: actualizar badge si hay un empleado seleccionado
      var selector = document.getElementById('selector-colaborador');
      if (selector && selector.value) {
        var empId = selector.value;
        fetch('/incentives/semana/?emp=' + empId + '&semana=' + SEMANA_INICIO)
          .then(function(r) { return r.json(); })
          .then(function(sd) {
            if (!sd.ok) return;
            var misteryReg = sd.registros.find(function(r) { return r.tipo === 'Mistery'; });
            actualizarBadgeMisteryManager(!!misteryReg, misteryReg ? misteryReg.monto : null);
          });
      }
    });
}

// ── DOM Ready ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {

  // Sincronizar bono de Venta y Mistery según datos externos
  if (typeof SEMANA_INICIO !== 'undefined') {
    syncVentaSemana();
    syncMisterySemana();
  }

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

  // Selector de evaluado Mistery (gerente)
  var evaluadoSelect = document.getElementById('mistery-evaluado-select');
  if (evaluadoSelect && typeof PERIODO_CERRADO !== 'undefined' && !PERIODO_CERRADO) {
    evaluadoSelect.addEventListener('change', function() {
      var empId = this.value || null;
      fetch('/incentives/marcar-evaluado-mistery/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({ emp_id: empId ? parseInt(empId) : null, week_start: SEMANA_INICIO }),
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.ok) {
          Swal.fire({ icon: 'error', title: 'Error', text: data.error || 'No se pudo guardar', confirmButtonColor: '#0d6efd' });
          return;
        }
        // Recargar el colaborador seleccionado para actualizar su total de Mistery
        var colSelector = document.getElementById('selector-colaborador');
        if (colSelector && colSelector.value) {
          cargarSemanaManager(colSelector.value);
        }
      })
      .catch(function() {
        Swal.fire({ icon: 'error', title: 'Error', text: 'Error de conexión', confirmButtonColor: '#0d6efd' });
      });
    });
  }

  // Selectores de evaluado Mistery (admin — uno por estación)
  if (typeof PERIODO_CERRADO !== 'undefined' && !PERIODO_CERRADO) {
    document.querySelectorAll('.mistery-evaluado-admin-select').forEach(function(sel) {
      sel.addEventListener('change', function() {
        var teamKey = this.dataset.teamKey;
        var empId   = this.value || null;
        fetch('/incentives/marcar-evaluado-mistery/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          body: JSON.stringify({ emp_id: empId ? parseInt(empId) : null, week_start: SEMANA_INICIO, team_key: teamKey }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (!data.ok) {
            Swal.fire({ icon: 'error', title: 'Error', text: data.error || 'No se pudo guardar', confirmButtonColor: '#0d6efd' });
            return;
          }
          // Refrescar badges de empleados expandidos en esa estación
          var detailRow = document.querySelector('.incentives-detail-row[data-team-key="' + teamKey + '"]');
          if (!detailRow) return;
          detailRow.querySelectorAll('.zona-emp-row.zona-expanded').forEach(function(row) {
            var eId = row.dataset.empId;
            if (!eId) return;
            fetch('/incentives/semana/?emp=' + eId + '&semana=' + SEMANA_INICIO)
              .then(function(r) { return r.json(); })
              .then(function(sd) {
                if (!sd.ok) return;
                var misteryReg = sd.registros.find(function(r) { return r.tipo === 'Mistery'; });
                actualizarBadgeMistery(eId, !!misteryReg, misteryReg ? misteryReg.monto : null);
              });
          });
        })
        .catch(function() {
          Swal.fire({ icon: 'error', title: 'Error', text: 'Error de conexión', confirmButtonColor: '#0d6efd' });
        });
      });
    });
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
          if (dieselMarcados > _CFG_DIESEL_MAX()) {
            this.checked = false;
            Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_DIESEL_MAX() + ' días de Diesel por semana (tope $' + _topeDiesel() + ')', confirmButtonColor: '#0d6efd' });
            return;
          }
          if (dieselMarcados === 1) {
            var cbManager = this;
            Swal.fire({
              icon: 'info',
              title: 'Incentivo Diesel',
              html: 'El incentivo de Diesel <strong>solo aplica para el primer y segundo turno</strong>.',
              confirmButtonColor: '#0d6efd',
              confirmButtonText: 'Entendido',
            }).then(function() {
              _doToggleFetch(cbManager, empId, tipo);
              actualizarTotal(tipo);
            });
            return;
          }
        }

        if (tipo === 'Encargado' && this.checked) {
          var encargadoMarcados = document.querySelectorAll('.incentivo-check[data-tipo="Encargado"]:checked').length;
          if (encargadoMarcados > _CFG_ENC_MAX()) {
            this.checked = false;
            Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_ENC_MAX() + ' días de Encargado por semana (tope $' + _topeEncargado() + ')', confirmButtonColor: '#0d6efd' });
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
            if (data.max_diesel) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_DIESEL_MAX() + ' días de Diesel por semana (tope $' + _topeDiesel() + ')', confirmButtonColor: '#0d6efd' });
            if (data.max_encargado) Swal.fire({ icon: 'warning', title: 'Límite alcanzado', text: 'Máximo ' + _CFG_ENC_MAX() + ' días de Encargado por semana (tope $' + _topeEncargado() + ')', confirmButtonColor: '#0d6efd' });
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
