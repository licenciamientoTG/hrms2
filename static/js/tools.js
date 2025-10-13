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
