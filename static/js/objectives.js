(function(){
// --- Tabs (mismo patrón de Solicitudes) ---
  const tabs = [
    {btn: document.getElementById('tab-mios'),    box: document.getElementById('contenedor-mios')},
    {btn: document.getElementById('tab-equipo'),  box: document.getElementById('contenedor-equipo')},
    {btn: document.getElementById('tab-general'), box: document.getElementById('contenedor-general')}
  ];
  tabs.forEach(({btn, box}) => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => { t.btn.classList.remove('active'); t.box.style.display='none'; });
      btn.classList.add('active'); box.style.display='';
    });
  });

  // --- Filtro simple (idéntica UX al de Solicitudes) ---
  const q = document.getElementById('objSearch');
  const list = document.getElementById('list-mios');
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
    empty.classList.toggle('d-none', shown !== 0);
  }
  q.addEventListener('input', apply);
})();

(function(){
  // Toggle descripción
  document.getElementById('btnDesc').addEventListener('click', () => {
    document.getElementById('descBox').classList.toggle('d-none');
  });

  // Chips de responsables (demo)
  const owners = new Set(["Diana Cano"]);
  const chipsWrap   = document.getElementById('ownersChips');
  const ownersInput = document.getElementById('ownersInput');
  const ownersHidden= document.getElementById('ownersHidden');
  const ownersBox   = document.getElementById('ownersBox');

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
})();