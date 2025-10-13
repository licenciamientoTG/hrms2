document.addEventListener("DOMContentLoaded", () => {
  fetch("/courses/unread_count/")
    .then(res => res.json())
    .then(data => {
      const count = data.unread_count;
      const badge = document.getElementById("new-courses-count");
      if (count > 0) {
        badge.textContent = count;
        badge.classList.remove("d-none");
      }
    });
});

// static/js/notifications.js
(function () {
  // ========= Config =========
  const PAGE_SIZE = 20;
  const URL_LIST      = "/notifications/api/notifications/";                 // GET ?page=&page_size=
  const URL_MARK_ALL  = "/notifications/api/notifications/mark-all-read/";   // POST
  const URL_MARK_READ = (id) => `/notifications/api/notifications/${id}/read/`; // POST
  const POLL_MS = 30000; // solo para el badge

  // ========= Estado =========
  let notifPage = 1;
  let notifHasNext = true;
  let notifLoading = false;

  // ========= DOM =========
  const dropdownTgl  = document.getElementById("alertsDropdown");
  const menuEl       = document.querySelector("#alertsDropdownWrapper .dropdown-menu");
  const listEl       = document.getElementById("alertsList");
  const loadMoreBtn  = document.getElementById("loadMoreNotifications");
  const loadingEl    = document.getElementById("alertsLoading");
  const markAllBtn   = document.getElementById("markAllRead");
  const badgeEl      = document.getElementById("new-courses-count");

  // ========= Utils =========
  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? m.pop() : "";
  }
  function toggleLoading(show, text = "Cargando...") {
    if (loadingEl) {
      loadingEl.textContent = text;
      loadingEl.classList.toggle("d-none", !show);
    }
    if (loadMoreBtn) loadMoreBtn.disabled = !!show;
  }
  function showBadge(count) {
    if (!badgeEl) return;
    const n = Number(count) || 0;
    badgeEl.textContent = String(n);
    badgeEl.classList.toggle("d-none", n === 0);
  }

  // === Render de un item con clases de estado (is-unread / is-read)
  function renderItem(n) {
    const a = document.createElement("a");
    a.className = "list-group-item list-group-item-action " + (n.is_read ? "is-read" : "is-unread");
    a.href   = n.url || "#";
    a.target = n.url ? "_blank" : "_self";
    a.rel    = n.url ? "noopener" : "";
    a.dataset.id = n.id;

    a.innerHTML = `
      <div class="d-flex justify-content-between">
        <span class="title">${n.title || ""}</span>
        <small class="text-muted">${new Date(n.created_at).toLocaleString()}</small>
      </div>
      ${n.body ? `<div class="small text-muted mt-1">${n.body}</div>` : ""}
    `;
    return a;
  }

  // ========= Fetch paginado =========
  async function fetchPage(page = 1) {
    if (!listEl || notifLoading) return;
    notifLoading = true;
    toggleLoading(true);

    try {
      const res = await fetch(`${URL_LIST}?page=${page}&page_size=${PAGE_SIZE}`, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!res.ok) {
        console.error("HTTP", res.status, await res.text());
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();

      if (page === 1) listEl.innerHTML = "";

      const items = Array.isArray(data.items) ? data.items : [];
      if (items.length === 0 && page === 1) {
        listEl.innerHTML = '<div class="text-center text-muted py-3">Sin notificaciones</div>';
      } else {
        items.forEach(n => listEl.appendChild(renderItem(n)));
      }

      notifPage    = data.page || page;
      notifHasNext = !!data.has_next;
      showBadge(data.count || 0);

      if (loadMoreBtn) {
        loadMoreBtn.disabled  = !notifHasNext;
        loadMoreBtn.textContent = notifHasNext ? "Ver más" : "No hay más";
      }
    } catch (err) {
      console.error("Error cargando notificaciones:", err);
      toggleLoading(true, "Error al cargar");
      setTimeout(() => toggleLoading(false), 1200);
    } finally {
      notifLoading = false;
      toggleLoading(false);
    }
  }

  // ========= Polling solo del badge =========
  async function pollBadge() {
    try {
      const res = await fetch(`${URL_LIST}?page=1&page_size=1`, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!res.ok) return;
      const data = await res.json();
      showBadge(data.count || 0);
    } catch (_) {}
  }

  // ========= Eventos =========

  // No cerrar el dropdown por clics internos
  menuEl?.addEventListener("click", (e) => e.stopPropagation());
  if (dropdownTgl && window.bootstrap?.Dropdown) {
    new bootstrap.Dropdown(dropdownTgl, { autoClose: 'outside' });
  }

  // Cargar primera página al abrir el dropdown
  dropdownTgl?.addEventListener("show.bs.dropdown", () => {
    notifPage = 1;
    notifHasNext = true;
    if (loadMoreBtn) {
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "Ver más";
    }
    fetchPage(1);
  });

  // Botón "Ver más" (evita cierre del dropdown)
  loadMoreBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (notifHasNext && !notifLoading) fetchPage(notifPage + 1);
  });

  // Marcar todas como leídas → cambia clases en UI + badge
  markAllBtn?.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const resp = await fetch(URL_MARK_ALL, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: "{}",
      });
      const data = await resp.json();
      if (data?.ok) {
        listEl?.querySelectorAll(".list-group-item.is-unread").forEach(el => {
          el.classList.remove("is-unread");
          el.classList.add("is-read");
        });
        showBadge(0);
      }
    } catch (err) {
      console.error("Error marcando todas:", err);
    }
  });

  // Click en item → marcar leído (clase) y luego navegar/persistir
  listEl?.addEventListener("click", async (ev) => {
    const a = ev.target.closest("a[data-id]");
    if (!a) return;
    ev.preventDefault();
    ev.stopPropagation();

    const id = a.dataset.id;
    const href = a.getAttribute("href") || "#";

    // UI inmediata
    if (a.classList.contains("is-unread")) {
      a.classList.remove("is-unread");
      a.classList.add("is-read");
      // actualizar badge local
      if (badgeEl && !badgeEl.classList.contains("d-none")) {
        const current = parseInt(badgeEl.textContent || "0", 10) || 0;
        showBadge(Math.max(0, current - 1));
      }
    }

    // Persistir en backend (best-effort)
    try {
      await fetch(URL_MARK_READ(id), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: "{}",
      });
    } catch (_) {}

    if (href && href !== "#") window.location.href = href;
  });

  // Arranque: solo badge (la lista se pinta al abrir)
  pollBadge();
  setInterval(pollBadge, POLL_MS);
})();

// límites y claves
const KEY = 'uiScalePercent';
const DEFAULT_SIZE = 100;

const htmlEl = document.documentElement;
const range = document.getElementById('uiScaleRange');
const value = document.getElementById('uiScaleValue');
const preview = document.getElementById('uiScalePreview');

// Cargar preferencia al iniciar
(function initUiScale(){
  const stored = parseInt(localStorage.getItem(KEY) || DEFAULT_SIZE, 10);
  applyScale(stored);
})();

function applyScale(percent){
  htmlEl.style.fontSize = percent + '%';
  if (range) range.value = percent;
  if (value) value.textContent = percent + '%';
  if (preview) preview.style.fontSize = percent + '%';
}

// Slider en vivo
range?.addEventListener('input', e => applyScale(parseInt(e.target.value, 10)));

// Presets
document.querySelectorAll('.preset').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    applyScale(parseInt(btn.dataset.size, 10));
  });
});

// Guardar
document.getElementById('uiScaleSave')?.addEventListener('click', ()=>{
  localStorage.setItem(KEY, String(range.value));
  // Si tienes backend, también puedes enviar via fetch para guardarlo por usuario.
});

// Restablecer
document.getElementById('uiScaleReset')?.addEventListener('click', ()=>{
  applyScale(DEFAULT_SIZE);
});
