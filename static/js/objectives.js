// ==== BLOQUE DEL PANEL (solo si existen los nodos) ====
(function(){
  // Tabs
  const tabs = [
    {btn: document.getElementById('tab-mios'),    box: document.getElementById('contenedor-mios')},
    {btn: document.getElementById('tab-equipo'),  box: document.getElementById('contenedor-equipo')},
    {btn: document.getElementById('tab-general'), box: document.getElementById('contenedor-general')}
  ].filter(t => t.btn && t.box); // <- evita nulls

  if (tabs.length) {
    tabs.forEach(({btn, box}) => {
      btn.addEventListener('click', () => {
        tabs.forEach(t => { t.btn.classList.remove('active'); t.box.style.display='none'; });
        btn.classList.add('active'); box.style.display='';
      });
    });
  }

  // Filtro simple
  const q    = document.getElementById('objSearch');
  const list = document.getElementById('list-mios');

  if (q && list) {
    const items = Array.from(list.querySelectorAll('.form-item')).filter(x => x.id !== 'obj-empty');
    const empty = document.getElementById('obj-empty');

    function apply(){
      const term = (q.value||'').trim().toLowerCase();
      let shown = 0;
      items.forEach(it => {
        const hay = (it.dataset.search || it.textContent).toLowerCase().includes(term);
        it.classList.toggle('d-none', !hay);
        if (hay) shown++;
      });
      if (empty) empty.classList.toggle('d-none', shown !== 0);
    }
    q.addEventListener('input', apply);
  }
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