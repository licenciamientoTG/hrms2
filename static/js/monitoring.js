// Tooltips (igual)
if (window.bootstrap) {
  document.querySelectorAll('.usage-week .day').forEach(el => {
    if (!bootstrap.Tooltip.getInstance(el)) new bootstrap.Tooltip(el);
  });
}

(function(){
  const input = document.getElementById('monitoring-search') || document.querySelector('input[name="q"]');
  if (!input) return;

  // evita submit default
  input.closest('form')?.addEventListener('submit', e => { e.preventDefault(); go(); });

  const debounce = (fn, ms=350) => { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; };

  function go(){
    const url = new URL(window.location.href);
    const term = (input.value || '').trim();
    if (term) url.searchParams.set('q', term);
    else url.searchParams.delete('q');

    // Reinicia a la primera página para ver TODOS los matches
    url.searchParams.delete('page');

    window.location.assign(url); // ← pide al servidor los resultados filtrados
  }

  input.addEventListener('input', debounce(go, 350));
  input.addEventListener('keydown', e => { if (e.key === 'Escape'){ input.value=''; go(); }});
})();
