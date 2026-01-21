(() => {
  // ===== Helpers =====
  const $ = (s) => document.querySelector(s);
  const bound = new WeakMap();
  function bindOnce(el, type, handler, opts) {
    if (!el || !type) return;
    const key = type + '|' + (opts?.capture ? '1' : '0');
    const set = bound.get(el) || new Set();
    if (set.has(key)) return;
    el.addEventListener(type, handler, opts);
    set.add(key);
    bound.set(el, set);
  }

  // ===== ADMIN: color / cover / puntos / confeti =====
  const colorPicker   = $('#colorPicker');
  const colorSwatch   = $('#colorSwatch');
  const colorHexLbl   = $('#colorHexLabel');
  const coverPreview  = $('#coverPreview');
  const coverImage    = $('#coverImage');
  const coverInput    = $('#coverInput');
  const confettiSwitch= $('#confettiSwitch');

  const pointsSwitch  = $('#pointsSwitch');
  const pointsBadge   = $('#pointsBadge');
  const pointsInput   = document.querySelector('input[name="points"]');
  const pointsValue   = $('#pointsValue');

  function applyColor(){
    const hex = (colorPicker?.value || '#1E3361').toUpperCase();
    if (colorSwatch)  colorSwatch.style.background = hex;
    if (colorHexLbl)  colorHexLbl.textContent = hex;
    if (coverPreview) coverPreview.style.background = hex;
  }
  function applyPoints(){
    if (!pointsBadge) return;
    const on = pointsSwitch ? !!pointsSwitch.checked : false;
    pointsBadge.style.display = on ? 'inline-block' : 'none';
    if (pointsValue) pointsValue.textContent = pointsInput?.value?.trim() || '0';
  }
  function toggleConfetti(){
    if (!coverImage) return;
    const hasFile = !!coverInput?.files?.length;
    const on = !!confettiSwitch?.checked;
    coverImage.style.display = (on || hasFile) ? 'block' : 'none';
  }

  colorPicker   && colorPicker.addEventListener('input', applyColor);
  pointsSwitch  && pointsSwitch.addEventListener('change', applyPoints);
  pointsInput   && pointsInput.addEventListener('input',  applyPoints);
  confettiSwitch&& confettiSwitch.addEventListener('change', toggleConfetti);
  coverInput    && coverInput.addEventListener('change', (e)=>{
    const f = e.target.files?.[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = ev => { if (coverImage){ coverImage.src = ev.target.result; coverImage.style.display='block'; } };
    r.readAsDataURL(f);
  });
  applyColor(); applyPoints(); toggleConfetti();

  // ===== USUARIO: modal comunicado =====
  const modalEl   = $('#newRecognitionModal');
  const openInput = $('#openNewRec');
  if (modalEl && window.bootstrap?.Modal) {
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    openInput && openInput.addEventListener('focus', () => bsModal.show());
    openInput && openInput.addEventListener('click',  () => bsModal.show());
    if (modalEl.dataset.reopen === '1') bsModal.show();
  }

  // Categoría → color
  const categorySelect = $('#categorySelect');
  const catColorBox    = $('#catColorBox');
  function applyCatColor(){
    if (!categorySelect || !catColorBox) return;
    const opt = categorySelect.options[categorySelect.selectedIndex];
    catColorBox.style.background = opt?.dataset?.color || '#E9ECEF';
  }
  categorySelect && categorySelect.addEventListener('change', applyCatColor);
  applyCatColor();

  // Estado botón Publicar
  const recipientsSelect = $('#recipientsSelect');
  const publishBtn       = $('#publishBtn');
  function updatePublishState(){
    const haveCategory   = !!categorySelect && !!categorySelect.value;
    if (publishBtn) publishBtn.disabled = !( haveCategory);
  }
  recipientsSelect && recipientsSelect.addEventListener('change', () => {
    const selected = Array.from(recipientsSelect.selectedOptions);
    if (selected.length > 30) {
      selected.at(-1).selected = false;
      alert('Máximo 30 colaboradores.');
    }
    updatePublishState();
  });
  categorySelect && categorySelect.addEventListener('change', updatePublishState);
  updatePublishState();

  // ===== Dropzone (múltiples imágenes, ACUMULANDO) =====
  (function() {
    const dropZone    = $('#dropZone');
    const mediaInput  = $('#mediaInput');
    const pickFileBtn = $('#pickFileBtn');
    const preview     = $('#previewArea');

    const MAX_MB = 10;
    const isImg  = f => f && f.type?.startsWith('image/');

    // Estado acumulado en memoria
    let selected = [];

    function syncInputAndRender() {
      // Actualiza <input.files> desde selected
      const dt = new DataTransfer();
      selected.forEach(f => dt.items.add(f));
      mediaInput.files = dt.files;

      // Render
      preview.innerHTML = '';
      selected.forEach(file => {
        const url = URL.createObjectURL(file);
        const fig = document.createElement('figure');
        fig.className = 'm-0';
        fig.style.width = '110px';
        fig.innerHTML = `
          <img src="${url}" class="img-fluid rounded border" style="height:84px;object-fit:cover;width:100%;">
          <figcaption class="small text-truncate" title="${file.name}">${file.name}</figcaption>`;
        preview.appendChild(fig);
      });
    }

    function addFiles(fileList) {
      const incoming = [...(fileList || [])]
        .filter(f => isImg(f) && f.size <= MAX_MB * 1024 * 1024);

      // Evita duplicados por (name,size,lastModified)
      const key = f => `${f.name}|${f.size}|${f.lastModified}`;
      const current = new Set(selected.map(key));

      incoming.forEach(f => { if (!current.has(key(f))) selected.push(f); });
      if (selected.length) syncInputAndRender();
    }

    pickFileBtn && pickFileBtn.addEventListener('click', () => mediaInput?.click());
    mediaInput  && mediaInput.addEventListener('change', e => addFiles(e.target.files));

    ['dragenter','dragover'].forEach(ev =>
      dropZone && dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add('border-primary'); })
    );
    ['dragleave','drop'].forEach(ev =>
      dropZone && dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.remove('border-primary'); })
    );
    dropZone && dropZone.addEventListener('drop', e => addFiles(e.dataTransfer?.files));
  })();



  // Mensaje solo texto (anti-HTML/pegado de archivos)
  document.querySelectorAll('textarea[name="message"]').forEach(tx => {
    bindOnce(tx, 'paste', (e) => {
      if ([...e.clipboardData?.items || []].some(i => i.kind === 'file')) {
        e.preventDefault(); errorMsg('Solo texto en el mensaje.');
      }
    });
    bindOnce(tx, 'input', (e) => { e.target.value = e.target.value.replace(/<[^>]*>/g,''); });
  });
})();


(function(){
  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  const csrftoken = getCookie('csrftoken');

  document.querySelectorAll('.js-del-cat').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const catName   = form.dataset.catName || 'esta categoría';
      const inUse     = form.dataset.inuse === '1';
      const toggleUrl = form.dataset.toggleUrl;   // <-- viene del HTML

      if (inUse) {
        const r = await Swal.fire({
          icon: 'warning',
          title: 'No se puede eliminar',
          html: `
            <div class="text-start">
              <p><strong>${catName}</strong> ya que fue utilizada como comunicado.</p>
              <p>Puedes <strong>desactivarla</strong> para impedir su uso futuro.</p>
            </div>`,
          showCancelButton: true,
          confirmButtonText: 'Desactivar',
          cancelButtonText: 'Cancelar',
        });
        if (r.isConfirmed && toggleUrl) {
          try {
              const resp = await fetch(toggleUrl, {
                method: 'POST',
                headers: {
                  'X-CSRFToken': csrftoken,
                  'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: 'force_deactivate=1'
              });
            if (!resp.ok) throw new Error();
            await Swal.fire({ icon:'success', title:'Desactivada', timer:1200, showConfirmButton:false });
            location.reload();
          } catch {
            Swal.fire({ icon:'error', title:'Ups', text:'No se pudo desactivar. Intenta más tarde.' });
          }
        }
        return;
      }

      const r = await Swal.fire({
        icon: 'question',
        title: '¿Eliminar categoría?',
        html: `<div class="text-start">
                 <p>Se eliminará <strong>${catName}</strong>.</p>
                 <p>Esta acción no se puede deshacer.</p>
               </div>`,
        showCancelButton: true,
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#d33'
      });
      if (r.isConfirmed) form.submit();
    });
  });
})();

// ===== AJAX comentarios =====
(function () {
  // CSRF de Django
  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  const csrftoken = getCookie('csrftoken');

  // Crear comentario sin recargar
  document.querySelectorAll('.js-comment-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const url = form.getAttribute('action');
      const recId = form.dataset.recId;
      const input = form.querySelector('input[name="body"]');
      const text = (input.value || '').trim();
      if (!text) return;

      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
          },
          body: new URLSearchParams({ body: text }).toString()
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || 'Error');

        // Inyectar el nuevo comentario al final
        const list = document.querySelector('#comments-' + recId);
        list.insertAdjacentHTML('beforeend', data.html);

        // Actualizar contador y limpiar input
        const badge = document.querySelector('#ccount-' + recId);
        if (badge) badge.textContent = data.count;
        input.value = '';
      } catch (err) {
        console.error(err);
        alert('No se pudo publicar el comentario.');
      }
    });
  });

  // Delegado para borrar comentario sin recargar
  document.addEventListener('submit', async (e) => {
    const form = e.target.closest('.js-comment-del');
    if (!form) return;
    e.preventDefault();

    const recId = form.dataset.recId;
    const commentId = form.dataset.commentId;
    const url = form.getAttribute('action');

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || 'Error');

      // Quitar del DOM y actualizar contador
      const node = document.querySelector('#comment-' + commentId);
      if (node) node.remove();
      const badge = document.querySelector('#ccount-' + recId);
      if (badge) badge.textContent = data.count;
    } catch (err) {
      console.error(err);
      alert('No se pudo eliminar el comentario.');
    }
  });
})();

function getCookie(name){
  const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}

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
      credentials: 'same-origin' // <-- asegúrate que envíe cookies
    });

    // Si redirige (login), te mando ahí
    if (res.redirected) { window.location = res.url; return; }

    const ctype = (res.headers.get('content-type') || '').toLowerCase();
    const raw = await res.text();
    let data = null; try { data = JSON.parse(raw); } catch {}

    if (!res.ok || !data?.ok) {
      console.error('[like] status:', res.status, 'ctype:', ctype, 'body:', raw.slice(0, 500));
      throw new Error('Like failed');
    }

    const countEl = btn.querySelector('.like-count');
    if (countEl) countEl.textContent = data.count;
    btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
    btn.classList.toggle('btn-success', data.liked);
    btn.classList.toggle('btn-outline-secondary', !data.liked);

  } catch (err) {
    console.error(err);
    window.Swal?.fire({icon:'error', title:'No se pudo registrar tu like'});
  } finally {
    btn.disabled = false;
  }
});

// Offcanvas: ver likes
(function () {
  const off = document.getElementById('likesOffcanvas');
  if (!off) return;

  const likesList   = document.getElementById('likes-list');
  const likesLoader = document.getElementById('likes-loader');
  const likesEmpty  = document.getElementById('likes-empty');
  const likesCount  = document.getElementById('likes-count');
  const likesTitle  = document.getElementById('likesOffcanvasLabel');

  const show = (which) => {
    likesLoader.classList.toggle('d-none', which !== 'loader');
    likesEmpty.classList.toggle('d-none', which !== 'empty');
    likesList.classList.toggle('d-none', which !== 'list');
  };

  async function fetchLikes(url) {
    show('loader'); likesList.innerHTML=''; likesCount.textContent='0';

    try {
      const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });

      if (!res.ok) {
        console.error('HTTP', res.status, await res.text().catch(()=>'')); 
        throw new Error('HTTP ' + res.status);
      }
      const ctype = (res.headers.get('content-type') || '').toLowerCase();
      if (!ctype.includes('application/json')) {
        console.error('Respuesta no JSON', await res.text().catch(()=>'')); 
        throw new Error('not-json');
      }

      const data = await res.json();
      likesTitle.textContent = data.title ? `Likes: ${data.title}` : 'Likes';
      likesCount.textContent = data.count ?? 0;

      if (!Array.isArray(data.items) || data.items.length === 0) { show('empty'); return; }

      const frag = document.createDocumentFragment();
      for (const it of data.items) {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex align-items-center gap-3';
        const icon = document.createElement('span'); icon.className = 'fs-4'; icon.textContent = '👍';
        const wrap = document.createElement('div');
        const strong = document.createElement('strong'); strong.textContent = it.name || '—';
        const small = document.createElement('small'); small.className = 'text-muted d-block'; small.textContent = it.liked_at || '';
        wrap.appendChild(strong); wrap.appendChild(small);
        li.appendChild(icon); li.appendChild(wrap);
        frag.appendChild(li);
      }
      likesList.appendChild(frag);
      show('list');

    } catch (e) {
      likesEmpty.textContent = 'No se pudieron cargar los likes.';
      show('empty');
    }
  }

  document.addEventListener('click', (e) => {
    const a = e.target.closest('.btn-view-likes');
    if (!a) return;
    e.preventDefault();
    const url = a.getAttribute('data-url');
    if (url) fetchLikes(url);
  });
})();

document.addEventListener('DOMContentLoaded', () => {
  const qInput = document.getElementById('recognitions-search');       // 👈 id único
  const table  = document.getElementById('admin-recognition-table');
  if (!qInput || !table) return;

  // Evita submit al presionar Enter
  qInput.closest('form')?.addEventListener('submit', e => e.preventDefault());

  let t = null;
  qInput.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(filterTable, 120);
  });

  function filterTable() {
    const term = (qInput.value || '').trim().toLowerCase();
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    let visible = 0;

    rows.forEach(tr => {
      // primera columna = título
      const title = (tr.querySelector('td:first-child')?.textContent || '').toLowerCase();
      const show = !term || title.includes(term);
      tr.classList.toggle('d-none', !show);
      if (show) visible++;
    });

    // fila “sin resultados”
    let emptyRow = table.querySelector('tbody .js-empty-row');
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.className = 'js-empty-row d-none';
      emptyRow.innerHTML = `<td colspan="3" class="text-center text-muted">Sin resultados.</td>`;
      table.querySelector('tbody').appendChild(emptyRow);
    }
    emptyRow.classList.toggle('d-none', visible !== 0);
  }

  filterTable(); // por si entras con ?q
});

(function(){
  const chkEmail = document.getElementById('notify_email');
  const chs = document.querySelectorAll('input[name="email_channels"]');
  function toggle(){ chs.forEach(c=> c.disabled = !chkEmail.checked); }
  chkEmail && chkEmail.addEventListener('change', toggle);
  toggle();
})();

(function() {
  let loading = false;
  const feed = document.getElementById('feed');
  const sentinel = document.getElementById('sentinel');
  if (!sentinel || !feed) return;

  // Lee de data-attributes (inyectados por Django)
  let nextPage = (function(){
    const v = sentinel.dataset.nextPage;
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? n : null;
  })();

  function buildNextUrl(page) {
    const url = new URL(window.location.href);
    url.searchParams.set('page', page);
    return url.pathname + url.search;
  }

  function loadMore() {
    if (loading || nextPage === null) return;
    loading = true;

    $.ajax({
      url: buildNextUrl(nextPage),
      dataType: 'json',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      success: function(resp) {
        if (resp && resp.html) {
          $('#feed').append(resp.html);
        }
        if (resp && resp.has_next) {
          nextPage = resp.next_page;
        } else {
          $('#sentinel').replaceWith('<div id="end-feed" class="text-center text-muted py-3">No hay más resultados</div>');
          io.disconnect();
          nextPage = null;
        }
      },
      complete: function() { loading = false; }
    });
  }

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => { if (entry.isIntersecting) loadMore(); });
  }, { rootMargin: '600px 0px' });

  io.observe(sentinel);
})();


$(document).ready(function() {
    // AL ABRIR EL MODAL: Cargar lista
    const modalEl = document.getElementById('scheduledModal');
    if (modalEl) {
      modalEl.addEventListener('show.bs.modal', function () {
        loadScheduledList();
      });
    }

    function loadScheduledList() {
        $('#scheduled-list-container').html('<div class="spinner-border text-primary"></div> Cargando...');
        
        // Ajusta la URL según tu urls.py
        $.get("/recognitions/scheduled/", function(data) {
            $('#scheduled-list-container').html(data);
        }).fail(function() {
            $('#scheduled-list-container').html('<p class="text-danger">Error al cargar.</p>');
        });
    }

    $(document).on('click', '.js-delete-scheduled', function() {
        const id = $(this).data('id');
        if(!confirm('¿Seguro que deseas cancelar esta publicación?')) return;

        // 1. OBTENER EL TOKEN REAL DESDE EL HTML
        // Buscamos cualquier input oculto de csrf que Django haya puesto en tus formularios
        const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

        $.post("/recognitions/delete/" + id + "/", {
            csrfmiddlewaretoken: csrfToken // <--- Usamos la variable, no el tag {{ }}
        }, function(res) {
            if(res.ok) {
                // Efecto visual de borrado
                $('#row-' + id).fadeOut(function(){ $(this).remove(); });
                
                // Opcional: Recargar la lista si quedó vacía
                if($('tbody tr:visible').length <= 1) {
                    loadScheduledList(); 
                }
            } else {
                alert('Error al eliminar');
            }
        }).fail(function() {
            alert('Error de servidor al intentar eliminar.');
        });
    });
});


$(document).ready(function() {
    // Verificar si la URL tiene un parámetro "highlight"
    const urlParams = new URLSearchParams(window.location.search);
    const highlightId = urlParams.get('highlight');

    if (highlightId) {
        const targetId = '#recognition-' + highlightId;
        const $target = $(targetId);

        if ($target.length) {
            // 1. Scroll suave hasta el elemento
            $('html, body').animate({
                scrollTop: $target.offset().top - 100 // -100 para dejar espacio arriba
            }, 1000);

            // 2. Efecto de "Glow" o borde temporal
            $target.css('transition', 'box-shadow 0.5s ease-in-out');
            $target.css('box-shadow', '0 0 15px rgba(13, 110, 253, 0.6)'); // Brillo azul
            $target.css('border-color', '#0d6efd');

            // Quitar el brillo después de 3 segundos
            setTimeout(function() {
                $target.css('box-shadow', '');
                $target.css('border-color', '');
            }, 3000);
        }
    }
});



// En recognition.js

function viewFullImage(imgUrl) {
    // 1. Imprimir en consola para ver si llega bien la ruta
    console.log("--> URL recibida:", imgUrl);

    var modalImg = document.getElementById('img-viewer-src');
    
    if (modalImg) {
        // 2. Asignar la URL
        modalImg.src = imgUrl;
        
        var modalEl = document.getElementById('imageViewerModal');
        // Asegurarse de usar bootstrap global
        var myModal = new bootstrap.Modal(modalEl);
        myModal.show();
    } else {
        console.error("Error: No se encontró la etiqueta <img id='img-viewer-src'> en el HTML");
    }
}