(function () {
  // Helpers
  const $  = (s, c=document) => c.querySelector(s);
  const $$ = (s, c=document) => Array.from(c.querySelectorAll(s));
  const debounce = (fn, ms=120) => { let t; return (...a)=>{clearTimeout(t); t=setTimeout(()=>fn(...a),ms);} };

  // CSRF desde cookie
  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
  }
  const csrfToken = getCookie('csrftoken');

  // ---- Filtro en vivo + “Sin resultados”
  const input   = document.getElementById('users-search') || document.getElementById('searchUsuarios');
  const clearBn = document.getElementById('users-clear');
  const table   = document.getElementById('admin-users-table');

  if (input && table) {
    const tbody = table.querySelector('tbody');
    const rows  = $$('tbody tr', table);

    let emptyRow = tbody.querySelector('.js-empty-row');
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.className = 'js-empty-row d-none';
      emptyRow.innerHTML = `<td colspan="${table.querySelectorAll('thead th').length||1}" class="text-center text-muted">Sin resultados.</td>`;
      tbody.appendChild(emptyRow);
    }

    const applyFilter = () => {
      const term = (input.value||'').trim().toLowerCase();

      const url = new URL(window.location.href);
      if (term) { url.searchParams.set('q', term); url.searchParams.delete('page'); }
      else { url.searchParams.delete('q'); }
      window.history.replaceState({}, '', url);
      if (clearBn) clearBn.classList.toggle('d-none', !term);

      let visible = 0;
      rows.forEach(tr => {
        const name = (tr.querySelector('.name')?.textContent||'').toLowerCase();
        const user = (tr.children[1]?.textContent||'').toLowerCase();
        const show = !term || name.includes(term) || user.includes(term);
        tr.classList.toggle('d-none', !show);
        if (show) visible++;
      });
      emptyRow.classList.toggle('d-none', visible !== 0);
    };

    input.addEventListener('input', debounce(applyFilter, 120));
    if (clearBn) clearBn.addEventListener('click', () => { input.value=''; input.focus(); applyFilter(); });
    applyFilter();
  }

  // ---- Toggle estado (delegación)
  const toggleUrl =
    table?.dataset.toggleUrl ||
    document.querySelector('meta[name="toggle-url"]')?.content || null;

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-toggle-status');
    if (!btn || !toggleUrl) return;

    const userId = btn.dataset.userId;
    if (!userId) return;

    btn.disabled = true;
    try {
      const res = await fetch(toggleUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken || '',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: 'user_id=' + encodeURIComponent(userId)
      });

      // Manejo de errores: si no es JSON, lee texto para ver qué pasó
      const ct = res.headers.get('Content-Type') || '';
      if (!res.ok) {
        const errtxt = ct.includes('application/json') ? JSON.stringify(await res.json()) : await res.text();
        throw new Error(`HTTP ${res.status}: ${errtxt}`);
      }

      const data = ct.includes('application/json') ? await res.json() : {};
      if (data.status !== 'ok') throw new Error('Respuesta no OK');

      const row   = document.getElementById('row-' + userId);
      const badge = row?.querySelector('.status-badge');
      const text  = row?.querySelector('.status');

      if (data.is_active) {
        if (badge) { badge.classList.remove('bg-secondary'); badge.classList.add('bg-success'); badge.textContent='Activo'; }
        if (text)  text.textContent = '✅ Activo';
        btn.textContent = 'Desactivar';
      } else {
        if (badge) { badge.classList.remove('bg-success'); badge.classList.add('bg-secondary'); badge.textContent='Inactivo'; }
        if (text)  text.textContent = '🚫 Inactivo';
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

document.addEventListener("DOMContentLoaded", function () {
  const filtroInput = document.getElementById("searchUsuarios");
  const rows = document.querySelectorAll(".user-table tbody tr");
  const pagination = document.getElementById("pagination");
  const itemsPerPage = 10;

  let filtroTexto = "";
  let currentPage = 1;

  function applyFilters() {
    let visibles = [];

    rows.forEach(row => {
      const name = row.querySelector('.name')?.innerText.toLowerCase() || '';
      const username = row.querySelector('td:nth-child(2)')?.innerText.toLowerCase() || '';

      const matchTexto = name.includes(filtroTexto) || username.includes(filtroTexto);

      if (matchTexto) {
        visibles.push(row);
      }

      row.style.display = "none";
    });

    renderPage(visibles, currentPage);
    renderPagination(visibles);
  }

  function renderPage(rowsFiltradas, page) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;

    rowsFiltradas.forEach((row, i) => {
      row.style.display = (i >= start && i < end) ? "" : "none";
    });
  }

  function renderPagination(rowsFiltradas) {
    const totalPages = Math.ceil(rowsFiltradas.length / itemsPerPage);
    pagination.innerHTML = "";

    if (totalPages <= 1) return;

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement("button");
      btn.className = `btn btn-sm mx-1 ${i === currentPage ? "btn-primary" : "btn-outline-primary"}`;
      btn.textContent = i;
      btn.addEventListener("click", () => {
        currentPage = i;
        renderPage(rowsFiltradas, i);
        renderPagination(rowsFiltradas);
      });
      pagination.appendChild(btn);
    }
  }

  filtroInput.addEventListener("input", function () {
    filtroTexto = this.value.toLowerCase().trim();
    currentPage = 1;
    applyFilters();
  });

  applyFilters();
});

