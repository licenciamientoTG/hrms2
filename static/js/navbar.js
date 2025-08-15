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
  // ==== Config rápida: cambia esto si tus rutas son distintas ====
  const API_BASE = "/notifications/api";
  const URL_LIST = `${API_BASE}/notifications/`;
  const URL_MARK_ALL = `${API_BASE}/notifications/mark-all-read/`;
  const URL_MARK_READ = `${API_BASE}/notifications/:id/read/`; // ← Nuevo
  const POLL_MS = 30000;

  // ==== Elementos del DOM ====
  const badge = document.getElementById("new-courses-count");
  const list = document.getElementById("alertsList");
  const markAllBtn = document.getElementById("markAllRead");
  const dropdownToggle = document.getElementById("alertsDropdown");

  // ==== Utilidades ====
  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? m.pop() : "";
  }

  function timeSince(iso) {
    try {
      const d = new Date(iso);
      const s = Math.floor((Date.now() - d.getTime()) / 1000);
      if (s < 60) return `${s}s`;
      const m = Math.floor(s / 60);
      if (m < 60) return `${m}m`;
      const h = Math.floor(m / 60);
      if (h < 24) return `${h}h`;
      const dd = Math.floor(h / 24);
      return `${dd}d`;
    } catch {
      return "";
    }
  }

  function showBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove("d-none");
    } else {
      badge.classList.add("d-none");
    }
  }

  function renderList(items) {
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '<div class="text-center text-muted py-3">Sin notificaciones</div>';
      return;
    }
    list.innerHTML = items
      .map(
        (n) => `
        <a href="${n.url || '#'}"
            class="list-group-item list-group-item-action d-flex gap-2 ${n.is_read ? 'is-read' : 'is-unread'}"
            data-id="${n.id}">
          <div class="flex-grow-1">
            <div>${n.title}</div>
            ${n.body ? `<div class="small text-muted">${n.body}</div>` : ""}
            <div class="small text-muted">${timeSince(n.created_at)}</div>
          </div>
        </a>`
      )
      .join("");

    if (window.feather) feather.replace();
  }


  async function fetchNotifications() {
    try {
      const res = await fetch(URL_LIST, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (data.ok === false) throw new Error("Respuesta no ok");
      showBadge(data.count || 0);
      renderList(data.items || []);
    } catch (e) {}
  }

  async function markAllRead() {
    try {
      await fetch(URL_MARK_ALL, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: "{}",
      });
      fetchNotifications();
    } catch (e) {}
  }

  // ==== Eventos ====
  if (markAllBtn) {
    markAllBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      markAllRead();
    });
  }

  // Nuevo: clic en notificación individual
  if (list) {
    list.addEventListener("click", async (ev) => {
      const a = ev.target.closest("a[data-id]");
      if (!a) return;

      ev.preventDefault();
      const id = a.dataset.id;
      const href = a.getAttribute("href") || "#";

      // Cambiar visualmente a "leído"
      if (a.classList.contains('is-unread')) {
        a.classList.remove('is-unread');
        a.classList.add('is-read');

        // Actualizar badge
        if (badge && !badge.classList.contains('d-none')) {
          const current = parseInt(badge.textContent || '0', 10) || 0;
          const next = Math.max(0, current - 1);
          if (next > 0) {
            badge.textContent = next;
          } else {
            badge.classList.add('d-none');
          }
        }
      }

      // Marcar en backend
      try {
        await fetch(URL_MARK_READ.replace(":id", id), {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: "{}",
        });
      } catch (e) {}

      if (href && href !== "#") {
        window.location.href = href;
      }
    });
  }


  document.addEventListener("shown.bs.dropdown", function (ev) {
    if (dropdownToggle && ev.target === dropdownToggle) {
      fetchNotifications();
    }
  });

  fetchNotifications();
  setInterval(fetchNotifications, POLL_MS);
})();
