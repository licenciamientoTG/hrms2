(function () {
  // regla de negocio: 50% del fondo
  const RATIO = 0.50;

  const $input = document.getElementById('fondo_ahorro');
  const $max = document.getElementById('max_prestamo');
  const $pct = document.getElementById('porcentaje');
  const $maxEls = document.querySelectorAll('.js-max-prestamo');

  // formateador a moneda
  const fmt = new Intl.NumberFormat('es-MX', {
    style: 'currency', currency: 'MXN', maximumFractionDigits: 0
  });

  // evita caracteres no numéricos en algunos navegadores
  $input.addEventListener('keydown', (e) => {
    if (['e','E','+','-','.'].includes(e.key)) e.preventDefault();
  });

  const actualizar = () => {
    const base = parseInt($input.value.replace(/\D+/g,'')) || 0;
    const max = Math.floor(base * RATIO);
    $max.textContent = fmt.format(max);
    $pct.textContent = Math.round(RATIO * 100) + '%';
    $maxEls.forEach(el => { el.textContent = fmt.format(max); });
  };

  $input.addEventListener('input', actualizar);
  actualizar(); // inicial
})();

(function () {
  const RATIO     = 0.50;       // 50% del fondo
  const CAP_FONDO = 200000;     // tope absoluto $200,000

  const $fondo   = document.getElementById('fondo_ahorro');
  const $monto   = document.getElementById('monto');
  const $pct     = document.getElementById('porcentaje');
  const $maxEls  = document.querySelectorAll('.js-max-prestamo');
  const $help    = document.getElementById('montoHelp');

  if (!$fondo || !$monto) return;

  const fmt = new Intl.NumberFormat('es-MX', { style:'currency', currency:'MXN', maximumFractionDigits:0 });

  // Bloquear e/E + - . en ambos inputs
  [$fondo, $monto].forEach(inp => inp.addEventListener('keydown', e => {
    if (['e','E','+','-','.'].includes(e.key)) e.preventDefault();
  }));

  let maxCache = 0;

  const toggleMonto = (enabled) => {
    $monto.disabled = !enabled;
    $monto.placeholder = enabled ? 'Escribe el monto...' : 'Ingresa primero tu fondo';
    if (!enabled) {
      $monto.value = '';
      if ($help) $help.classList.add('d-none');
    }
  };

  // Recalcula tope a partir del fondo y aplica clamp a 200,000
  const actualizarTope = () => {
    let base = parseInt(($fondo.value || '').replace(/\D+/g,''), 10) || 0;

    // clamp [0, CAP_FONDO] y reflejar en el input
    if (base < 0) base = 0;
    if (base > CAP_FONDO) {
      base = CAP_FONDO;
      $fondo.value = String(CAP_FONDO);
    }

    // pintar tope (50%) y porcentaje
    const max = Math.floor(base * RATIO);
    maxCache = max;

    $maxEls.forEach(el => el.textContent = fmt.format(max));
    if ($pct) $pct.textContent = Math.round(RATIO * 100) + '%';

    // habilitar el campo monto solo si base >= 2
    toggleMonto(base >= 2);

    // setear atributo max nativo y recortar si se pasó
    $monto.max = String(max);
    const val = parseInt(($monto.value || '').replace(/\D+/g,''), 10);
    if (!isNaN(val) && val > max) $monto.value = max || '';
  };

  // Validación en vivo del monto solicitado (sin impedir teclear)
  const validarMontoEnInput = () => {
    if ($monto.disabled) return;
    let val = parseInt(($monto.value || '').replace(/\D+/g,''), 10);
    if (isNaN(val)) { $monto.value = ''; return; }
    if (val < 0) val = 0;
    if (maxCache > 0 && val > maxCache) val = maxCache;
    $monto.value = String(val);
  };

  // (Reemplaza tu función y deja igual los demás handlers)
  const ajustarStepEnBlur = () => {
    if ($monto.disabled) return;
    let val = parseInt($monto.value || '0', 10);
    if (isNaN(val)) { $monto.value = ''; return; }
    if (val < 0) val = 0;
    if (maxCache > 0 && val > maxCache) val = maxCache;
    $monto.value = String(val); // sin redondear a múltiplos de 100
  };


  // Eventos
  $fondo.addEventListener('input', actualizarTope);
  $monto.addEventListener('input', validarMontoEnInput);
  $monto.addEventListener('blur', ajustarStepEnBlur);

  // Inicial
  actualizarTope();
})();

(function () {
  // Formateador con DOS decimales
  const fmt2 = new Intl.NumberFormat('es-MX', {
    style: 'currency', currency: 'MXN',
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });

  const $monto        = document.getElementById('monto');
  const $semanas      = document.getElementById('semanas');
  const $pagoSemanal  = document.getElementById('pago_semanal');

  if (!$monto || !$semanas || !$pagoSemanal ) return;

  const calcularPago = () => {
    if ($monto.disabled) return;

    const monto   = parseInt(($monto.value || '').replace(/\D+/g,''), 10) || 0;
    const semanas = parseInt($semanas.value || '0', 10) || 0;

    if (monto <= 0 || semanas <= 0) {
      $pagoSemanal.textContent = fmt2.format(0);
      return;
    }

    // Pago con 2 decimales
    const pago = Math.round((monto / semanas) * 100) / 100;
    $pagoSemanal.textContent = fmt2.format(pago);
  };

  $semanas.addEventListener('change', calcularPago);
  $monto.addEventListener('input', calcularPago);

  calcularPago();
})();



// ====== Formateadores ======
const MXN2 = new Intl.NumberFormat('es-MX', {
  style: 'currency', currency: 'MXN',
  minimumFractionDigits: 2, maximumFractionDigits: 2
});
const fmtDate = d => d.toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' });

// Lunes de la semana de "hoy"
function startOfThisWeek() {
  const d = new Date();                           // hoy (hora local del navegador)
  const copy = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = (copy.getDay() + 6) % 7;           // 0 = lunes, 6 = domingo
  copy.setDate(copy.getDate() - diff);            // nos vamos al lunes
  return copy;
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function renderDesglose() {
  const $monto   = document.getElementById('monto');
  const $semanas = document.getElementById('semanas');
  const $panel   = document.getElementById('detalle-contenido');
  const $btnEnviar = document.getElementById('btn-enviar-solicitud');
  const $inputWeek = document.getElementById('server-current-week');
  const serverWeek = $inputWeek ? $inputWeek.value : '--';

  if (!$monto || !$semanas || !$panel) return;

  const total = parseInt(($monto.value || '').replace(/\D+/g,''), 10) || 0;
  const weeks = parseInt(($semanas.value || '0'), 10) || 0;

  if ($monto.disabled || total <= 0 || weeks <= 0) {
    $panel.innerHTML = `<p class="text-muted mb-0">Indica un monto y semanas para ver el desglose.</p>`;
    if ($btnEnviar) $btnEnviar.style.display = 'none';
    return;
  }

  // ===== Reparto exacto por centavos =====
  const totalCents = Math.round(total * 100);
  const baseCents  = Math.floor(totalCents / weeks);
  let leftover     = totalCents - baseCents * weeks;

  let saldoCents = totalCents;
  const rows = [];

  // ELIMINADO: Ya no calculamos week0Start ni fechas de calendario

  for (let i = 0; i < weeks; i++) {
    const pagoCents = baseCents + (leftover > 0 ? 1 : 0);
    if (leftover > 0) leftover--;

    saldoCents -= pagoCents;

    const pago  = pagoCents / 100;
    const saldo = Math.max(saldoCents / 100, 0);

    // CAMBIO AQUI: En lugar de fechas, mostramos el número de semana (1, 2, 3...)
    const numSemana = i + 1;

    rows.push(`
      <tr>
        <td class="text-center">${numSemana}</td>
        <td class="text-end">${MXN2.format(pago)}</td>
        <td class="text-end">${MXN2.format(saldo)}</td>
      </tr>
    `);
  }

  $panel.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-2">
      <div class="small text-muted">Semanas: <strong>${weeks}</strong></div>
      <div class="small text-muted">Monto total: <strong>${MXN2.format(total)}</strong></div>
    </div>
    <div class="table-responsive">
      <table class="table table-sm table-striped align-middle mb-2 desglose-table">
        <thead class="table-light">
          <tr>
            <th class="text-center" style="width: 54%;">#Semana</th>
            <th class="text-end"    style="width: 23%;">Pago</th>
            <th class="text-end"    style="width: 23%;">Saldo pendiente</th>
          </tr>
        </thead>
        <tbody>
          ${rows.join('')}
        </tbody>
        <tfoot>
          <tr>
            <th class="text-end" colspan="2">Total</th>
            <th class="text-end">${MXN2.format(total)}</th>
          </tr>
        </tfoot>
      </table>
    </div>
    <p class="text-muted small mb-0">
      La información que se muestra queda sujeta a revisión. <br>
      Semana actual: <strong>${serverWeek}</strong>.<br>
      Recuerda que el deposito será en la semana 44
    </p>
  `;

  // ✅ MOSTRAR EL BOTÓN
  if ($btnEnviar) {
      $btnEnviar.style.display = 'inline-block';
  }
}

// --- Actualizar desglose cuando cambian datos ---
document.getElementById('monto')?.addEventListener('input', renderDesglose);
document.getElementById('monto')?.addEventListener('blur',  renderDesglose);
document.getElementById('semanas')?.addEventListener('change', renderDesglose);
document.getElementById('semanas')?.addEventListener('input',  renderDesglose);

// --- También al abrir/cerrar el panel de detalles ---
document.getElementById('btn-detalles')?.addEventListener('click', function () {
  const wrap = document.getElementById('calc-layout');
  const opened = wrap.classList.toggle('show-details');
  this.textContent = opened ? 'Ocultar detalles' : 'Ver detalles';
  this.setAttribute('aria-expanded', opened ? 'true' : 'false');
  if (opened) renderDesglose();
});

document.addEventListener('DOMContentLoaded', function() {
    
    // Función para obtener el CSRF Token (necesario para POST en Django)
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

    // Lógica para enviar la solicitud
    const btnEnviar = document.getElementById('btn-enviar-solicitud');
    
    if (btnEnviar) {
        // Usamos clonación para asegurar que no haya listeners duplicados si se recarga el script
        const nuevoBtn = btnEnviar.cloneNode(true);
        btnEnviar.parentNode.replaceChild(nuevoBtn, btnEnviar);
        
        nuevoBtn.addEventListener('click', function() {
            // 1. Obtener valores
            const inputMonto = document.getElementById('monto');
            const selectSemanas = document.getElementById('semanas');
            
            if (!inputMonto || !selectSemanas) return;

            // Limpiar valores (quitar símbolos no numéricos)
            const rawMonto = inputMonto.value.replace(/[^0-9.]/g, '');
            const monto = parseFloat(rawMonto);
            const semanas = parseInt(selectSemanas.value);

            // 2. Validaciones básicas
            if (isNaN(monto) || monto <= 0) {
                Swal.fire('Error', 'Por favor ingresa un monto válido.', 'error');
                return;
            }
            if (isNaN(semanas) || semanas <= 0) {
                Swal.fire('Error', 'Selecciona un plazo de semanas válido.', 'error');
                return;
            }

            // 3. Confirmación visual con SweetAlert2
            Swal.fire({
                title: '¿Confirmar solicitud?',
                html: `Solicitarás <b>$${monto.toLocaleString('es-MX')}</b> a pagar en <b>${semanas} semanas</b>. <p><br>Al enviar esta solicitud despues del jueves a las 12:00 pm el prestamo se procesará hasta la siguiente semana.</p>`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Sí, enviar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    // 4. Enviar datos al servidor
                    nuevoBtn.disabled = true;
                    nuevoBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';

                    fetch('/tools/api/create-loan/', {  // Asegúrate de que esta URL coincida con urls.py
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify({
                            amount: monto,
                            weeks: semanas
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.ok) {
                            Swal.fire(
                                '¡Solicitud Enviada!',
                                'Tu solicitud ha sido registrada correctamente.',
                                'success'
                            ).then(() => {
                                // Recargar página o limpiar
                                window.location.reload(); 
                            });
                        } else {
                            Swal.fire('Error', data.error || 'Ocurrió un error al procesar la solicitud.', 'error');
                            nuevoBtn.disabled = false;
                            nuevoBtn.innerHTML = 'Enviar solicitud';
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        Swal.fire('Error', 'Error de conexión con el servidor.', 'error');
                        nuevoBtn.disabled = false;
                        nuevoBtn.innerHTML = 'Enviar solicitud';
                    });
                }
            });
        });
    }
});

(function () {
  const $select = document.getElementById('semanas');
  const $limitInput = document.getElementById('server-max-weeks');
  const $monto = document.getElementById('monto');
  const $btn = document.getElementById('btn-detalles');

  // Si no hay input hidden, no limitamos nada
  if (!$limitInput) return;

  const maxAllowed = parseInt($limitInput.value, 10);

  // CASO 1: Periodo Cerrado (Semana 44)
  if (maxAllowed <= 0) {
      if ($monto) {
          $monto.disabled = true;
          $monto.value = "";
          $monto.placeholder = "Periodo cerrado (Semana 44)";
          const $help = document.getElementById('montoHelp');
          if ($help) $help.classList.add('d-none');
      }
      if ($select) $select.disabled = true;
      if ($btn) $btn.disabled = true;
      return;
  }

  // CASO 2: Periodo Restringido (Ej. Semana 43 -> Solo 1 semana)
  if ($select) {
      // Recorremos de atrás para adelante para borrar sin romper índices
      for (let i = $select.options.length - 1; i >= 0; i--) {
          const val = parseInt($select.options[i].value, 10);
          if (val > maxAllowed) {
              $select.remove(i); 
          }
      }
      
      // Corregir selección inválida si el usuario tenía algo seleccionado
      if (parseInt($select.value, 10) > maxAllowed) {
          $select.value = "1";
          // Disparamos evento change para recalcular pagos
          $select.dispatchEvent(new Event('change'));
      }
  }
})();