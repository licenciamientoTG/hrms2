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

(function(){
  const steps = Array.from(document.querySelectorAll('.js-step'));
  const tabs  = Array.from(document.querySelectorAll('.js-step-tab'));
  const prev  = document.getElementById('btnPrev');            // <a> con href a obj_cycles_admin
  const next  = document.querySelector('.js-next');
  const finish= document.querySelector('.js-finish');
  const dots  = [1,2,3].map(n => document.querySelector('.step-'+n));
  const limitSwitch = document.getElementById('limitSwitch');
  const limitBox = document.getElementById('limitBox');

  let current = 1;

  function show(step){
    current = step;

    // Mostrar/ocultar paso y activar pestañas/dots
    steps.forEach(s => s.classList.toggle('d-none', s.dataset.step != step));
    tabs.forEach(t => t.classList.toggle('active', t.dataset.step == step));
    dots.forEach((d,i)=> d.classList.toggle('active', (i+1) <= step));

    // Next/Finish
    next.classList.toggle('d-none', step === 3);
    finish.classList.toggle('d-none', step !== 3);

    // Texto del botón prev
    // En paso 1 dice "Volver" (y usará el href); en otros dice "Anterior"
    prev.textContent = (step === 1) ? 'Volver' : 'Anterior';
  }

  function fillSummary(){
    const name  = document.querySelector('input[name="name"]').value || '—';
    const start = document.querySelector('input[name="start_date"]').value || '—';
    const end   = document.querySelector('input[name="end_date"]').value || '—';
    const minEl = document.querySelector('input[name="min_objectives"]');
    const maxEl = document.querySelector('input[name="max_objectives"]');

    document.getElementById('sumName').textContent  = name;
    document.getElementById('sumStart').textContent = start;
    document.getElementById('sumEnd').textContent   = end;

    if (limitSwitch.checked){
      const min = (minEl.value||'0'), max = (maxEl.value||'0');
      document.getElementById('sumLimit').textContent = `${min} – ${max}`;
    } else {
      document.getElementById('sumLimit').textContent = 'Ilimitados';
    }
  }

  // NEXT
  next.addEventListener('click', () => {
    if (current < 3) {
      if (current === 2) fillSummary();
      show(current + 1);
    }
  });

  // PREV: si estás en paso 1, deja navegar al href (volver);
  // si no, cancela navegación y muestra el paso anterior.
  prev.addEventListener('click', (e) => {
    if (current > 1) {
      e.preventDefault();
      show(current - 1);
    }
    // Si current === 1, no hacemos preventDefault: el <a> navega a obj_cycles_admin.
  });

  // Límite de objetivos on/off
  limitSwitch.addEventListener('change', () => {
    limitBox.classList.toggle('d-none', !limitSwitch.checked);
  });

  // Tabs solo visuales
  tabs.forEach(t => t.addEventListener('click', e => e.preventDefault()));

  show(1);
})();