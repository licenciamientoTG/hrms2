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

  // ===== USUARIO: modal reconocimiento =====
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
    const haveRecipients = !!recipientsSelect && recipientsSelect.selectedOptions.length > 0;
    const haveCategory   = !!categorySelect && !!categorySelect.value;
    if (publishBtn) publishBtn.disabled = !(haveRecipients && haveCategory);
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
              <p><strong>${catName}</strong> ya que fue utilizada como reconocimiento.</p>
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