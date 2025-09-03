(() => {
  // ===== Helpers =====
  const $ = (s) => document.querySelector(s);
  const bound = new WeakSet();
  function bindOnce(el, type, handler, opts) {
    if (!el || !type || bound.has(el)) return;
    el.addEventListener(type, handler, opts);
    bound.add(el);
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

  // ===== Dropzone (solo imágenes) — una sola vez =====
  const dropZone    = $('#dropZone');
  const mediaInput  = $('#mediaInput');
  const pickFileBtn = $('#pickFileBtn');
  const preview     = $('#previewArea');

  const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
  const EXT_WHITELIST = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'];

  function isImageFile(file){
    if (!file) return false;
    const mimeOk = file.type?.startsWith('image/');
    const extOk  = EXT_WHITELIST.some(ext => file.name?.toLowerCase().endsWith(ext));
    return mimeOk && extOk;
  }
  function errorMsg(msg){ window.Toastify ? Toastify({text:msg,duration:3500}).showToast() : alert(msg); }
  function clearSelection(){ if (mediaInput) mediaInput.value=''; if (preview) preview.innerHTML=''; }
  function showPreview(file){
    if (!preview) return;
    preview.innerHTML = '';
    const url = URL.createObjectURL(file);
    const img = document.createElement('img');
    img.src = url; img.alt='Vista previa';
    img.style.maxWidth='100%'; img.style.maxHeight='220px';
    preview.appendChild(img);
  }
  function handleFile(file){
    if (!file) return;
    if (!isImageFile(file)) { clearSelection(); return errorMsg('Solo se permiten imágenes.'); }
    if (file.size > MAX_BYTES){ clearSelection(); return errorMsg('La imagen excede 10 MB.'); }
    showPreview(file);
  }

  bindOnce(pickFileBtn, 'click', () => mediaInput?.click());
  bindOnce(mediaInput, 'change', (e)=> handleFile(e.target.files?.[0]));

  ['dragenter','dragover','dragleave','drop'].forEach(evt => {
    bindOnce(dropZone, evt, (e) => {
      e.preventDefault(); e.stopPropagation();
      if (evt === 'dragenter' || evt === 'dragover') dropZone.classList.add('bg-light');
      if (evt === 'dragleave' || evt === 'drop')     dropZone.classList.remove('bg-light');
    });
  });
  bindOnce(dropZone, 'drop', (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (!f) return;
    if (!isImageFile(f)) return errorMsg('Solo se permiten imágenes.');
    if (f.size > MAX_BYTES) return errorMsg('La imagen excede 10 MB.');
    if (mediaInput) mediaInput.files = e.dataTransfer.files;
    showPreview(f);
  });

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
