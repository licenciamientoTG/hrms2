// ==== BLOQUE DEL PANEL (busca en los 3 tabs) ====
(function () {
  // Tabs (igual que antes)
  const tabs = [
    { btn: document.getElementById('tab-mios'),    box: document.getElementById('contenedor-mios') },
    { btn: document.getElementById('tab-equipo'),  box: document.getElementById('contenedor-equipo') },
    { btn: document.getElementById('tab-general'), box: document.getElementById('contenedor-general') },
  ].filter(t => t.btn && t.box);

  if (tabs.length) {
    tabs.forEach(({ btn, box }) => {
      btn.addEventListener('click', () => {
        tabs.forEach(t => { t.btn.classList.remove('active'); t.box.style.display = 'none'; });
        btn.classList.add('active'); box.style.display = '';
        apply(); 
      });
    });
  }

  // Buscador
  const q = document.getElementById('objSearch');
  if (!q) return;

  // Listas a filtrar (una por tab)
  const lists = [
    document.getElementById('list-mios'),
    document.getElementById('list-equipo'),
    document.getElementById('list-general'),
  ].filter(Boolean);

  // Crea (si falta) una fila "Sin resultados" por lista
  function ensureEmptyRow(list) {
    let erow = list.querySelector('.js-empty-row');
    if (!erow) {
      erow = document.createElement('div');
      erow.className = 'form-item mb-3 js-empty-row d-none';
      erow.innerHTML = `
        <i class="form-icon bi bi-bullseye"></i>
        <div class="form-name">Sin resultados.</div>`;
      list.appendChild(erow);
    }
    return erow;
  }

  // Filtra una lista
  function filterList(list, term) {
    const emptyRow = ensureEmptyRow(list);
    const items = Array.from(list.querySelectorAll('.form-item'))
      .filter(el => !el.classList.contains('js-empty-row')); // no contamos el vacío

    let visible = 0;
    items.forEach(it => {
      const hay = (it.dataset.search || it.textContent).toLowerCase().includes(term);
      it.classList.toggle('d-none', !hay);
      if (hay) visible++;
    });
    emptyRow.classList.toggle('d-none', visible !== 0);
  }

  // Aplica sobre TODAS las listas (aunque estén ocultas); así, si cambias de tab, ya está filtrado
  function apply() {
    const term = (q.value || '').trim().toLowerCase();
    lists.forEach(list => filterList(list, term));
  }

  const debounce = (fn, ms = 150) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  q.addEventListener('input', debounce(apply, 150));
  apply(); // aplica al cargar
})();

// ==== BLOQUE DEL CREATE (solo si existen los nodos) ====
(function(){
  // Toggle descripción
  const btn = document.getElementById('btnDesc');
  const box = document.getElementById('descBox');

  function setOpen(open){
    box.classList.toggle('d-none', !open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.innerHTML = open
      ? '<i class="bi bi-dash-lg"></i> Ocultar descripción'
      : '<i class="bi bi-plus-lg"></i> Agregar descripción (opcional)';
    if (open) box.focus();
  }

  if (btn && box) {
    btn.addEventListener('click', () => setOpen(box.classList.contains('d-none')));
    // Si ya viene con texto (por validación), muéstrala
    if (box.value && box.value.trim()) setOpen(true);
  }

  // Chips de responsables (demo)
  const chipsWrap   = document.getElementById('ownersChips');
  const ownersInput = document.getElementById('ownersInput');
  const ownersHidden= document.getElementById('ownersHidden');
  const ownersBox   = document.getElementById('ownersBox');

  if (chipsWrap && ownersInput && ownersHidden && ownersBox) {
    const owners = new Set(["Diana Cano"]);

    function render(){
      chipsWrap.innerHTML = '';
      owners.forEach(n => {
        const el = document.createElement('span');
        el.className = 'chip';
        el.innerHTML = `<i class="bi bi-person"></i>${n}<span class="x bi bi-x" data-x="${n}"></span>`;
        chipsWrap.appendChild(el);
      });
      ownersHidden.value = Array.from(owners).join(',');
    }

    ownersInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ','){
        e.preventDefault();
        const v = ownersInput.value.trim().replace(/,$/,'');
        if (v) owners.add(v);
        ownersInput.value = '';
        render();
      }
    });

    ownersBox.addEventListener('click', e => {
      const x = e.target.dataset.x;
      if (x){ owners.delete(x); render(); ownersInput.focus(); }
    });

    render();
  }
})();

// ==== BLOQUE DEL WIZARD (solo si existen los nodos) ====
(function(){
  const steps = Array.from(document.querySelectorAll('.js-step'));
  const prev  = document.getElementById('btnPrev');
  const next  = document.querySelector('.js-next');
  const finish= document.querySelector('.js-finish');
  const limitSwitch = document.getElementById('limitSwitch');
  const limitBox = document.getElementById('limitBox');
  const tabs  = Array.from(document.querySelectorAll('.js-step-tab'));

  // ⛔ Si no estamos en la página del wizard, no hagas nada
  if (!steps.length || !prev || !next || !finish || !limitSwitch || !limitBox) return;

  let current = 1;

  function show(step){
    current = step;
    steps.forEach(s => s.classList.toggle('d-none', s.dataset.step != step));
    tabs.forEach(t => t.classList.toggle('active', t.dataset.step == step));
    [1,2,3].forEach((n,i) => {
      const d = document.querySelector('.step-'+n);
      if (d) d.classList.toggle('active', (i+1) <= step);
    });
    next.classList.toggle('d-none', step === 3);
    finish.classList.toggle('d-none', step !== 3);
    prev.textContent = (step === 1) ? 'Volver' : 'Anterior';
  }

  function fillSummary(){
    const name  = document.querySelector('input[name="name"]').value || '—';
    const start = document.querySelector('input[name="start_date"]').value || '—';
    const end   = document.querySelector('input[name="end_date"]').value || '—';
    const minEl = document.querySelector('input[name="min_objectives"]');
    const maxEl = document.querySelector('input[name="max_objectives"]');
    const sum = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    sum('sumName',  name);
    sum('sumStart', start);
    sum('sumEnd',   end);
    if (limitSwitch.checked){
      const min = (minEl?.value||'0'), max = (maxEl?.value||'0');
      sum('sumLimit', `${min} – ${max}`);
    } else {
      sum('sumLimit', 'Ilimitados');
    }
  }

  next.addEventListener('click', () => {
    if (current === 1) {
      const nameInput = document.querySelector('input[name="name"]');
      if (!nameInput.value.trim()) { nameInput.focus(); nameInput.reportValidity(); return; }
    }
    if (current < 3) {
      if (current === 2) fillSummary();
      show(current + 1);
    }
  });

  prev.addEventListener('click', (e) => {
    if (current > 1) { e.preventDefault(); show(current - 1); }
  });

  limitSwitch.addEventListener('change', () => {
    limitBox.classList.toggle('d-none', !limitSwitch.checked);
  });

  tabs.forEach(t => t.addEventListener('click', e => e.preventDefault()));

  show(1);
})();

(() => {
  const f = document.getElementById('cycleSearch');
  if (!f) return;
  const q = f.querySelector('input[name="q"]');
  const submit = () => (f.requestSubmit ? f.requestSubmit() : f.submit());
  let t;
  q.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(submit, 400); // 300 ms tras dejar de escribir
  });
})();

// confirmación + delete (AJAX si input[name="ajax"] == 1)
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.js-delete-cycle');
  if (!btn) return;

  const form = btn.closest('form.delete-cycle-form');
  const row  = btn.closest('tr');
  const name = btn.dataset.title || 'este ciclo';

  if (!confirm(`¿Eliminar "${name}"? Esta acción no se puede deshacer.`)) return;

  const useAjax = form.querySelector('input[name="ajax"]')?.value === '1';
  if (!useAjax) { form.submit(); return; }

  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

  fetch(form.action, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'X-CSRFToken': csrf,
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json',
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    },
    body: new URLSearchParams(new FormData(form))
  })
  .then(async (r) => {
    // Si hubo redirección (p.ej. a login) o status != 200 => error legible
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`HTTP ${r.status} ${r.statusText} - ${text.slice(0,120)}…`);
    }
    // intenta parsear JSON; si falla, también error
    const data = await r.json().catch(() => { throw new Error('Respuesta no es JSON'); });
    if (!data.ok) throw new Error(data.error || 'No se pudo eliminar');
    // OK
    row.remove();
  })
  .catch((err) => {
    // Si te manda al login/403/CSRF verás esto:
    console.error('Delete error:', err);
    alert('Error al eliminar. Revisa permisos y CSRF (ver consola).');
  });
});

(() => {
  const combo   = document.getElementById('ownersCombo');
  if (!combo) return;
  const head    = document.getElementById('ownersHead');
  const menu    = document.getElementById('ownersMenu');
  const summary = document.getElementById('ownersSummary');

  const open  = () => { menu.classList.add('open'); head.setAttribute('aria-expanded','true'); };
  const close = () => { menu.classList.remove('open'); head.setAttribute('aria-expanded','false'); };

  // Actualiza el texto de la “opción” visible como un select
  const updateSummary = () => {
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    if (!checks.length) { summary.textContent = 'Selecciona responsables…'; return; }
    const names = [];
    checks.forEach(cb => names.push(cb.closest('.owners-option').querySelector('strong')?.textContent.trim() || ''));
    summary.textContent = (names.length <= 2) ? names.join(', ') : `${names[0]}, ${names[1]} +${names.length-2} más`;
  };

  // Abrir/cerrar como un select normal
  head.addEventListener('click', () => menu.classList.contains('open') ? close() : open());
  document.addEventListener('click', e => { if (!combo.contains(e.target)) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  // Clic en fila: alterna el checkbox (sin CTRL)
  menu.addEventListener('click', (e) => {
    const row = e.target.closest('.owners-option'); if (!row) return;
    const cb  = row.querySelector('input[type="checkbox"]');
    if (e.target !== cb) cb.checked = !cb.checked;
    updateSummary();
  });

  // Inicializa el resumen (p.ej. si ya viene tildado el usuario actual)
  updateSummary();
})();