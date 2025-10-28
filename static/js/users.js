(function(){
  const input = document.getElementById('users-search');
  if (!input) return;

  const debounce = (fn, ms=1000) => { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; };

  function go(){
    const url  = new URL(window.location.href);
    const term = (input.value || '').trim();

    if (term) url.searchParams.set('q', term);
    else url.searchParams.delete('q');

    // volver a la primera página para ver todos los matches
    url.searchParams.delete('page');

    // conserva otros params (page_size, etc.) automáticamente
    window.location.assign(url);
  }

  input.addEventListener('input', debounce(go, 1000));
  input.form && input.form.addEventListener('submit', (e)=>{ e.preventDefault(); go(); });
  input.addEventListener('keydown', e => { if (e.key === 'Escape'){ input.value=''; go(); }});
})();

// --- Activar/Desactivar usuario (delegación restaurada)
(function(){
  const table = document.getElementById('admin-users-table');
  if (!table) return;

  const toggleUrl = table.dataset.toggleUrl;

  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  const csrfToken = getCookie('csrftoken');

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-toggle-status');
    if (!btn) return;              // no es el botón
    if (!toggleUrl) return;        // falta URL
    const userId = btn.dataset.userId;
    if (!userId) return;

    btn.disabled = true;
    try {
      const res = await fetch(toggleUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: 'user_id=' + encodeURIComponent(userId)
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (data.status !== 'ok') throw new Error('Respuesta no OK');

      const row   = document.getElementById('row-' + userId);
      const badge = row?.querySelector('.status-badge');

      if (data.is_active) {
        badge?.classList.remove('bg-secondary');
        badge?.classList.add('bg-success');
        if (badge) badge.textContent = 'Activo';
        btn.textContent = 'Desactivar';
      } else {
        badge?.classList.remove('bg-success');
        badge?.classList.add('bg-secondary');
        if (badge) badge.textContent = 'Inactivo';
        btn.textContent = 'Activar';
      }
    } catch (err) {
      console.error(err);
      alert('No se pudo cambiar el estado.');
    } finally {
      btn.disabled = false;
    }
  });
})();

function toggleStatus(userId) {
  fetch(toggleUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrfToken
    },
    body: "user_id=" + userId
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === "ok") {
      const row = document.getElementById("row-" + userId);
      const statusSpan = row.querySelector(".status");
      const button = row.querySelector("button");

      if (data.is_active) {
        statusSpan.textContent = "✅ Activo";
        button.textContent = "Desactivar";
      } else {
        statusSpan.textContent = "🚫 Inactivo";
        button.textContent = "Activar";
      }
    }
  });
}

