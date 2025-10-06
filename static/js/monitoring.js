  if (window.bootstrap) {
    document.querySelectorAll('.usage-week .day').forEach(el=>{
      new bootstrap.Tooltip(el);
    });
  }

(function(){
  const input = document.querySelector('input[name="q"]');
  if (!input) return;
  let t;
  input.addEventListener('input', function(){
    clearTimeout(t);
    t = setTimeout(() => {
      // reinicia a la página 1 al cambiar búsqueda
      const form = input.closest('form');
      if (!form) return;
      // elimina cualquier ?page= de la URL actual
      const url = new URL(window.location.href);
      url.searchParams.set('q', input.value);
      url.searchParams.delete('page');
      window.location.href = url.toString();
    }, 350); // debounce 350ms
  });
})();