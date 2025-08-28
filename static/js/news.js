document.addEventListener("DOMContentLoaded", function () {
  // ==== TinyMCE (solo en páginas que tienen el editor) ====
  const hasEditor = !!document.querySelector('textarea[name="content"]');
  if (hasEditor && window.tinymce) {
    tinymce.init({
      selector: 'textarea[name="content"]',
      height: 420,
      menubar: false,
      branding: false,
      promotion: false,
      language: 'es',
      plugins: 'lists link image media table emoticons charmap anchor code',
      toolbar: 'undo redo | bold italic underline | forecolor backcolor | ' +
               'fontsizeselect fontselect styles | alignleft aligncenter alignright alignjustify | ' +
               'numlist bullist | outdent indent | link anchor | media table | emoticons charmap | code',
      object_resizing: 'iframe',
      media_live_embeds: true,
      media_dimensions: true,
      extended_valid_elements: 'iframe[src|width|height|frameborder|allow|allowfullscreen]',
      content_style:
        "body{font-family:Inter,Arial,sans-serif;font-size:14px}" +
        ".embed-responsive{position:relative;width:100%;padding-bottom:56.25%;}" +
        ".embed-responsive iframe{position:absolute;top:0;left:0;width:100%;height:100%;}",
      setup(editor) {
        const form = document.getElementById("news-form");
        if (form) {
          form.addEventListener("submit", (e) => {
            tinymce.triggerSave();
            const plain = editor.getContent({ format: 'text' }).trim();
            if (!plain) { e.preventDefault(); alert("El contenido es obligatorio."); editor.focus(); }
          });
        }
      }
    });
  }

  // ==== SweetAlert2: eliminar noticia (lista admin) ====
  function getCookie(name){
    const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[1]) : '';
  }

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-delete-news');
    if (!btn) return;

    const form    = btn.closest('form');
    const row     = btn.closest('tr');
    const title   = btn.dataset.title || 'esta noticia';
    const useAjax = btn.dataset.ajax === '1';

    // Si SweetAlert no está, usa confirm nativo
    if (!window.Swal) {
      if (confirm(`¿Eliminar "${title}"? Esta acción no se puede deshacer.`)) {
        if (useAjax) {
          const fd = new FormData(form);
          fetch(form.action, { method:'POST', headers:{'X-CSRFToken':getCookie('csrftoken')}, body:fd })
            .then(r => { if (r.ok) row?.remove(); });
        } else {
          form.submit();
        }
      }
      return;
    }

    const resp = await Swal.fire({
      title: '¿Eliminar noticia?',
      html: `Se eliminará <b>${title}</b>.<br>Esta acción no se puede deshacer.`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Sí, eliminar',
      cancelButtonText: 'Cancelar',
      reverseButtons: true,
      focusCancel: true
    });
    if (!resp.isConfirmed) return;

    if (!useAjax) { form.submit(); return; }

    try {
      const fd = new FormData(form);
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: fd
      });
      if (!res.ok) throw new Error();
      row?.remove();
      Swal.fire({ icon:'success', title:'Eliminada', timer:1600, showConfirmButton:false });
    } catch {
      Swal.fire({ icon:'error', title:'No se pudo eliminar', text:'Inténtalo de nuevo.' });
    }
  });
});

document.addEventListener('DOMContentLoaded', () => {
  // ======== Filtro en vivo para USUARIOS (cards) ========
  (function () {
    const qInput = document.querySelector('input[name="q"]');
    const grid   = document.getElementById('news-grid');
    if (!qInput || !grid) return;

    // no recargar al presionar Enter
    qInput.closest('form')?.addEventListener('submit', (e) => e.preventDefault());

    const filtrarCards = () => {
      const term = (qInput.value || '').trim().toLowerCase();
      grid.querySelectorAll('.news-card').forEach(card => {
        const title = (card.querySelector('.card-title')?.textContent || '').toLowerCase();
        const show  = !term || title.includes(term);
        card.classList.toggle('d-none', !show);
      });
    };

    qInput.addEventListener('input', filtrarCards);
    filtrarCards(); // aplica si viene con ?q
  })();

  // ======== Filtro en vivo para ADMIN (tabla) ========
  (function () {
    const qInput = document.querySelector('input[name="q"]');
    const table  = document.getElementById('admin-news-table');
    if (!qInput || !table) return;

    // no recargar al presionar Enter
    qInput.closest('form')?.addEventListener('submit', (e) => e.preventDefault());

    const filtrarTabla = () => {
      const term = (qInput.value || '').trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(tr => {
        // primera columna = título
        const titleCell = tr.querySelector('td:first-child');
        const title     = (titleCell?.textContent || '').toLowerCase();
        const show      = !term || title.includes(term);
        tr.classList.toggle('d-none', !show);
      });
    };

    qInput.addEventListener('input', filtrarTabla);
    filtrarTabla(); // aplica si viene con ?q
  })();
});

function getCookie(name){
  const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}

// Toggle like (delegación global)
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-like');
  if (!btn) return;

  const url = btn.dataset.url;
  if (!url) return;

  btn.disabled = true;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
      // body opcional: new URLSearchParams() si quieres
    });

    // Si login_required te redirige al login
    if (res.redirected) { window.location = res.url; return; }

    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch (_) {}

    if (!res.ok || !data?.ok) {
      console.error('[like] status:', res.status, 'body:', text);
      // Mensajes útiles según el caso:
      if (res.status === 403 && /CSRF/i.test(text)) {
        if (window.Swal) Swal.fire({icon:'error', title:'CSRF', text:'Falta token CSRF. Recarga la página.'});
      } else if (res.status === 404) {
        if (window.Swal) Swal.fire({icon:'error', title:'No encontrado'});
      } else {
        if (window.Swal) Swal.fire({icon:'error', title:'No se pudo registrar tu like'});
      }
      return;
    }

    // ✅ éxito: actualizar contador y estado visual
    const countEl = btn.querySelector('.like-count');
    if (countEl) countEl.textContent = data.count;

    btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
    btn.classList.toggle('is-active', data.liked);
    btn.classList.toggle('btn-outline-secondary', !data.liked);
    btn.classList.toggle('btn-success', data.liked); // opcional para resaltar
  } catch (err) {
    console.error('[like] fetch error:', err);
    if (window.Swal) Swal.fire({icon:'error', title:'No se pudo registrar tu like'});
  } finally {
    btn.disabled = false;
  }
});

// Utilidad CSRF (si no la tienes ya en news.js)
function getCookie(name){
  const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}

// --- Crear comentario (AJAX) ---
document.addEventListener('submit', async (e) => {
  const form = e.target.closest('#comment-form');
  if (!form) return;

  e.preventDefault();

  const url = form.dataset.url;
  const fd = new FormData(form);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
      , body: fd
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error();

    // prepend el nuevo comentario
    const wrap = document.getElementById('comments');
    wrap.insertAdjacentHTML('afterbegin', data.html);

    // limpiar textarea
    form.querySelector('textarea[name="body"]').value = '';

    // actualizar contador
    const cc = document.querySelector('.comment-count');
    if (cc) cc.textContent = data.count;

  } catch (err) {
    console.error(err);
    if (window.Swal) Swal.fire({icon:'error', title:'No se pudo publicar'});
  }
});

// --- Eliminar comentario (AJAX + SweetAlert) ---
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.js-delete-comment');
  if (!btn) return;

  e.preventDefault();
  const url = btn.dataset.url;

  const go = async () => {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]')?.value || '')
      }
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error();
    // eliminar del DOM
    const node = btn.closest('[id^="comment-"]');
    if (node) node.remove();
    // actualizar contador
    const cc = document.querySelector('.comment-count');
    if (cc) cc.textContent = data.count;
  };

  if (window.Swal) {
    const resp = await Swal.fire({
      title: '¿Eliminar comentario?',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Eliminar',
      cancelButtonText: 'Cancelar',
      reverseButtons: true,
      focusCancel: true
    });
    if (!resp.isConfirmed) return;

    try { await go(); }
    catch { Swal.fire({icon:'error', title:'No se pudo eliminar'}); }
  } else {
    if (!confirm('¿Eliminar comentario?')) return;
    try { await go(); } catch {}
  }
});

