// surveys/static/js/survey.js
// Builder de encuestas con editor de preguntas en modal (localStorage)

(function () {
  const strip = document.getElementById('sectionsStrip');
  if (!strip) return;

  const SURVEY_ID = strip.dataset.surveyId || 'new';
  const KEY = `survey:draft:${SURVEY_ID}`;

  const newSectionCol = document.getElementById('newSectionCol');
  const btnNewSection = document.getElementById('btnNewSection');

  const tplSection  = document.getElementById('tpl-section');
  const tplQuestion = document.getElementById('tpl-question');

  // ---------- STATE ----------
  function saveDraft(s){ localStorage.setItem(KEY, JSON.stringify(s)); }
  function normalize(s){
    s.version ||= 1;
    s.lastSeq ||= {section:0,question:0};
    s.sections ||= [];
    const optTypes = new Set(['single','multiple','dropdown']);
    s.sections.forEach(sec => {
      sec.questions ||= [];
      sec.questions.forEach(q => {
        q.type ||= 'single';
        q.required = !!q.required;
        ensureOptionsShape(q);
        ensureBranchShape(q);

      });
    });
    return s;
  }
  function loadDraft() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return normalize(JSON.parse(raw));
    } catch {}
    const init = {
      version: 1,
      lastSeq: { section: 1, question: 1 },
      sections: [{
        id: 's1',
        title: 'Sección 1',
        order: 1,
        go_to: null,
        questions: [{
          id: 'q1',
          title: 'Pregunta 1',
          type: 'single',
          required: false,
          order: 1,
          options: ['Opción 1']
        }]
      }]
    };
    saveDraft(init);
    return init;
  }
  let state = loadDraft();

  // ---------- HELPERS ----------
  function lblAfter(sec){ return `Después de la sección ${sec.order}`; }
  function jumpLabel(val){
    if (val === null || val === '') return 'Ir a la siguiente sección';
    if (val === 'submit') return 'Enviar el formulario';
    const s = state.sections.find(x => x.id === val);
    return s ? `Ir a la sección ${s.order} (${s.title || 'Sección'})` : 'Ir a la siguiente sección';
  }
  function renumberSectionsState(st){
    st.sections.sort((a,b)=>a.order-b.order).forEach((s,i)=>{ s.order = i+1; });
  }
  function renumberQuestionsState(sec){
    (sec.questions||[]).sort((a,b)=>a.order-b.order).forEach((q,i)=>{ q.order = i+1; });
  }
  function findQuestionById(qid) {
    for (const sec of state.sections) {
      const q = (sec.questions || []).find(x => x.id === qid);
      if (q) return { sec, q };
    }
    return null;
  }
  function ensureOptionsShape(q) {
    const optTypes = new Set(['single', 'multiple', 'dropdown']);
    if (optTypes.has(q.type)) {
      q.options ||= [];
      // MIGRACIÓN: si vienen como strings => volver objetos
      q.options = q.options.map(o => {
        if (typeof o === 'string') return { label: o, correct: false };
        // Asegura claves
        return { label: (o?.label ?? ''), correct: !!o?.correct };
      });
      if (!q.options.length) q.options = [{ label: 'Opción 1', correct: false }];
    } else {
      delete q.options;
    }
  }
  function renderQuestionPreview(node, q) {
    node.querySelectorAll('[data-preview]').forEach(el => el.remove());

    if (q.type === 'single') {
      const wrap = document.createElement('div');
      wrap.className = 'mt-1';
      wrap.dataset.preview = 'single';
      (q.options || [{label:'Opción 1', correct:false}]).forEach((opt, i) => {
        const div = document.createElement('div');
        div.className = 'form-check';
        div.innerHTML = `
          <input class="form-check-input correct-preview"
                type="radio"
                disabled
                name="p_${q.id}"
                ${opt.correct ? 'checked' : ''}>
          <label class="form-check-label">${opt.label || `Opción ${i+1}`}</label>`;
        wrap.appendChild(div);
      });
      node.insertBefore(wrap, node.querySelector('.q-footer'));
    }

    if (q.type === 'multiple') {
      const wrap = document.createElement('div');
      wrap.className = 'mt-1';
      wrap.dataset.preview = 'multiple';
      (q.options || [{label:'Opción 1', correct:false}]).forEach((opt, i) => {
        const div = document.createElement('div');
        div.className = 'form-check';
        div.innerHTML = `
          <input class="form-check-input correct-preview"
                type="checkbox"
                disabled
                ${opt.correct ? 'checked' : ''}>
          <label class="form-check-label">${opt.label || `Opción ${i+1}`}</label>`;
        wrap.appendChild(div);
      });
      node.insertBefore(wrap, node.querySelector('.q-footer'));
    }

    if (q.type === 'dropdown') {
      const wrap = document.createElement('div');
      wrap.className = 'mt-2';
      wrap.dataset.preview = 'dropdown';
      const sel = document.createElement('select');
      sel.className = 'form-select';
      sel.disabled = true;
      (q.options || [{label:'Opción 1', correct:false}]).forEach(opt => {
        const option = document.createElement('option');
        option.textContent = opt.label;
        if (opt.correct) option.textContent += ' (✔ correcta)';
        sel.appendChild(option);
      });
      wrap.appendChild(sel);
      node.insertBefore(wrap, node.querySelector('.q-footer'));
    }
  }



  // ---------- TEMPLATES: CLONE & BIND ----------
  function cloneSection(sec){
    const frag = tplSection.content.cloneNode(true);
    const col  = frag.querySelector('.section-col');

    col.dataset.sectionId = sec.id;

    const secTitle = frag.querySelector('[data-bind="sec-title"]');
    secTitle.textContent = sec.title || `Sección ${sec.order}`;

    // dropdown ids
    frag.querySelectorAll('[data-action="sec.rename"]').forEach(b => b.dataset.id = sec.id);
    frag.querySelectorAll('[data-action="sec.duplicate"]').forEach(b => b.dataset.id = sec.id);
    frag.querySelectorAll('[data-action="sec.delete"]').forEach(b => b.dataset.id = sec.id);

    // Nueva pregunta
    const linkAdd = frag.querySelector('[data-add-question]');
    linkAdd.dataset.section = sec.id;

    // footer labels & jump
    frag.querySelector('[data-bind="sec-after-label"]').textContent = lblAfter(sec);

    const jumpBtn = frag.querySelector('[data-section-jump]');
    jumpBtn.dataset.section = sec.id;
    jumpBtn.textContent = jumpLabel(sec.go_to);

    const jumpUl = frag.querySelector('[data-jump-menu]');
    jumpUl.dataset.section = sec.id;

    return col;
  }

  function cloneQuestion(q){
    ensureOptionsShape(q);

    const frag = tplQuestion.content.cloneNode(true);
    const node = frag.querySelector('.q-card');

    node.dataset.questionId = q.id;
    node.dataset.type = q.type || 'single';
    node.dataset.required = String(!!q.required);

    const titleEl = node.querySelector('[data-bind="q-title"]');
    titleEl.textContent = q.title || 'Pregunta';

    // --- CHIP de tipo ---
    const meta = typeMeta(q.type);
    const chip = document.createElement('span');
    chip.className = `qtype-chip ${meta.cls}`;
    chip.textContent = meta.short;
    chip.title = meta.long;
    chip.setAttribute('data-qtype-chip',''); // para actualizarlo en vivo
    titleEl.after(chip);

    node.querySelectorAll('[data-action="q.delete"]').forEach(b => b.dataset.id = q.id);

    renderQuestionPreview(node, q);
    return node;
  }


  // ---------- RENDER ----------
  function renderAll(){
    [...strip.querySelectorAll('.section-col')].forEach(c => { if (c !== newSectionCol) c.remove(); });

    const sections = [...state.sections].sort((a,b)=>a.order-b.order);
    sections.forEach(sec => {
      const col = cloneSection(sec);

      const list = col.querySelector('[data-bind="q-list"]');
      const qs   = [...(sec.questions||[])].sort((a,b)=>a.order-b.order);
      qs.forEach(q => list.appendChild(cloneQuestion(q)));

      strip.insertBefore(col, newSectionCol);
    });
  }

  function rerenderSection(secId){
    const sec = state.sections.find(s => s.id === secId);
    if (!sec) return;

    const oldCol = strip.querySelector(`.section-col[data-section-id="${sec.id}"]`);
    if (!oldCol) return;

    const col = cloneSection(sec);
    const list = col.querySelector('[data-bind="q-list"]');
    [...(sec.questions||[])].sort((a,b)=>a.order-b.order)
      .forEach(q => list.appendChild(cloneQuestion(q)));

    strip.replaceChild(col, oldCol);
  }

  // ---------- ACTIONS ----------
  function addSection(){
    const next = (state.lastSeq.section || 0) + 1;
    state.lastSeq.section = next;
    const order = Math.max(0, ...state.sections.map(s => s.order)) + 1;

    state.sections.push({ id:`s${next}`, title:`Sección ${order}`, order, go_to:null, questions:[] });
    saveDraft(state);
    renderAll();
    newSectionCol.scrollIntoView({behavior:'smooth', inline:'end'});
  }

  function addQuestion(sectionId){
    const sec = state.sections.find(s => s.id === sectionId);
    if (!sec) return;

    const nextQ = (state.lastSeq.question || 0) + 1;
    state.lastSeq.question = nextQ;
    const order = Math.max(0, ...(sec.questions||[]).map(q => q.order)) + 1;

    const q = {
      id:`q${nextQ}`,
      title:`Pregunta ${order}`,
      type:'single',
      required:false,
      order,
      options:[{ label:'Opción 1', correct:false }]
    };
    (sec.questions ||= []).push(q);

    saveDraft(state);
    rerenderSection(sec.id);
  }

  async function renameSection(sectionId){
    const sec = state.sections.find(s => s.id === sectionId);
    if (!sec) return;

    const { value, isConfirmed } = await Swal.fire({
      title: 'Renombrar sección',
      input: 'text',
      inputLabel: 'Nombre de la sección',
      inputValue: sec.title || `Sección ${sec.order}`,
      icon: 'question',
      width: 520,
      backdrop: 'rgba(15,23,42,.35)',     // overlay suave
      showCancelButton: true,
      confirmButtonText: 'Guardar',
      cancelButtonText: 'Cancelar',
      buttonsStyling: false,               // usamos clases Bootstrap
      focusConfirm: false,                 // mantenemos el foco en el input
      allowEnterKey: true,
      customClass: {
        popup: 'sa-modal',
        title: 'sa-title',
        inputLabel: 'sa-label',
        input: 'form-control sa-input',
        actions: 'sa-actions',
        confirmButton: 'btn btn-primary',
        cancelButton: 'btn btn-light ms-2'
      },
      didOpen: () => { Swal.getInput()?.select(); },
      preConfirm: (val) => {
        const v = (val || '').trim();
        if (!v) { Swal.showValidationMessage('Escribe un nombre'); return false; }
        if (v.length > 120) { Swal.showValidationMessage('Máximo 120 caracteres'); return false; }
        return v;
      }
    });

    if (!isConfirmed || !value) return;
    sec.title = value.trim();
    saveDraft(state);
    rerenderSection(sec.id);
  }

  // ---- eliminar sección ----
  async function deleteSectionById(sectionId){
    const ok = window.Swal
      ? (await Swal.fire({icon:'warning', title:'Eliminar sección', text:'Se eliminará la sección y sus preguntas.', showCancelButton:true, confirmButtonText:'Eliminar'})).isConfirmed
      : confirm('Se eliminará la sección y sus preguntas. ¿Continuar?');
    if(!ok) return;

    if (state.sections.length <= 1){
      window.Swal ? Swal.fire({icon:'info', title:'No puedes eliminar la única sección'})
                  : alert('No puedes eliminar la única sección');
      return;
    }

    state.sections = state.sections.filter(s => s.id !== sectionId);
    state.sections.forEach(s => { if (s.go_to === sectionId) s.go_to = null; });
    renumberSectionsState(state);
    saveDraft(state);
    renderAll();
    refreshJumpMenus();
  }

  // ---- eliminar pregunta ----
  async function deleteQuestionById(questionId){
    const ok = window.Swal
      ? (await Swal.fire({icon:'warning', title:'Eliminar pregunta', showCancelButton:true, confirmButtonText:'Eliminar'})).isConfirmed
      : confirm('¿Eliminar esta pregunta?');
    if(!ok) return;

    const sec = state.sections.find(s => (s.questions||[]).some(q => q.id === questionId));
    if(!sec) return;

    sec.questions = (sec.questions||[]).filter(q => q.id !== questionId);
    renumberQuestionsState(sec);
    saveDraft(state);
    rerenderSection(sec.id);
  }

  // build menú “Después de…”
  function buildJumpMenu(ul, sid){
    while (ul.firstChild) ul.removeChild(ul.firstChild);

    function add(value, label){
      const li = document.createElement('li');
      const b  = document.createElement('button');
      b.className = 'dropdown-item';
      b.textContent = label;
      b.dataset.value = value ?? '';
      b.dataset.section = sid;
      li.appendChild(b);
      ul.appendChild(li);
    }
    add('', 'Ir a la siguiente sección');
    [...state.sections].sort((a,b)=>a.order-b.order)
      .forEach(s => add(s.id, `Ir a la sección ${s.order} (${s.title || 'Sección'})`));
    add('submit', 'Enviar el formulario');
  }

  function refreshJumpMenus(){
    document.querySelectorAll('[data-jump-menu]').forEach(ul=>{
      buildJumpMenu(ul, ul.dataset.section);
    });
  }

  // ---------- EVENTS (builder) ----------
  btnNewSection?.addEventListener('click', addSection);

  document.addEventListener('click', (e) => {
    const add = e.target.closest('[data-add-question]');
    if (add) { e.preventDefault(); return addQuestion(add.dataset.section); }

    const item = e.target.closest('.dropdown-item');
    if (!item) return;

    if (item.dataset.action === 'sec.rename') return renameSection(item.dataset.id);
    if (item.dataset.action === 'sec.delete') return deleteSectionById(item.dataset.id || item.closest('.section-col')?.dataset.sectionId);
    if (item.dataset.action === 'q.delete')   return deleteQuestionById(item.dataset.id || item.closest('.q-card')?.dataset.questionId);
  });

  document.addEventListener('show.bs.dropdown', (e) => {
    const btn = e.target.closest('[data-section-jump]');
    if (!btn) return;
    const sid = btn.dataset.section;
    const ul  = btn.parentElement.querySelector('[data-jump-menu]');
    buildJumpMenu(ul, sid);
  });

  document.addEventListener('click', (e) => {
    const it = e.target.closest('[data-jump-menu] .dropdown-item');
    if (!it) return;
    const sid = it.dataset.section;
    const sec = state.sections.find(s => s.id === sid);
    if (!sec) return;
    const value = it.dataset.value || null;
    sec.go_to = value;
    saveDraft(state);
    const btn = it.closest('.dropdown').querySelector('[data-section-jump]');
    if (btn) btn.textContent = jumpLabel(value);
  });

  // ---------- MODAL: Editor de preguntas ----------
  const modalEl = document.getElementById('qEditor');
  const tInput  = document.getElementById('qeTitle');
  const rChk    = document.getElementById('qeRequired');
  const typeList = document.getElementById('qeTypeList');
  const optsWrap = document.getElementById('qeOptionsWrap');
  const optsList = document.getElementById('qeOptionsList');
  const btnAddOpt = document.getElementById('qeAddOption');
  const btnSave = document.getElementById('qeSave');
  const qeBranch = document.getElementById('qeBranch');

  let CURRENT_QID = null;
  let CURRENT_SEC_ID = null;
  const optTypes = new Set(['single', 'multiple', 'dropdown']);

  function branchAllowed(type){ return type === 'single' || type === 'dropdown'; }

  function buildBranchOptionsHTML(currentSectionId, selected){
    // Construye el <option> list para un destino
    const sections = [...state.sections].sort((a,b)=>a.order-b.order);
    const sel = (v) => (v === selected ? 'selected' : '');

    // Nota: value "" = Siguiente
    let html = `
      <option value="" ${sel(null)}>— Siguiente —</option>
      <option value="submit" ${sel('submit')}>Enviar formulario</option>
      <optgroup label="Secciones">
    `;
    sections.forEach(s => {
      html += `<option value="${s.id}" ${sel(s.id)}>Sección ${s.order} (${s.title || 'Sección'})</option>`;
    });
    html += '</optgroup>';
    return html;
  }

  // --- Normaliza ARIA al abrir y enfoca el primer control
  modalEl.addEventListener('show.bs.modal', () => {
    modalEl.removeAttribute('inert');
    modalEl.removeAttribute('aria-hidden');
  });
  modalEl.addEventListener('shown.bs.modal', () => {
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.removeAttribute('aria-hidden');
    tInput?.focus();
  });

  // --- Guardián: si el modal está visible no debe tener aria-hidden
  const ariaGuard = new MutationObserver(() => {
    if (modalEl.classList.contains('show') && modalEl.getAttribute('aria-hidden') === 'true') {
      modalEl.removeAttribute('aria-hidden');
      modalEl.setAttribute('aria-modal', 'true');
    }
  });
  ariaGuard.observe(modalEl, { attributes: true, attributeFilter: ['class','aria-hidden'] });

  // --- Mover foco fuera del modal antes de ocultarlo (evita el warning)
  function focusOutsideModal() {
    const target = document.querySelector(`.q-card[data-question-id="${CURRENT_QID}"]`) || document.body;
    if (target) {
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
      try { target.focus(); } catch {}
    }
  }
  modalEl.addEventListener('hide.bs.modal', focusOutsideModal);

  function typeMeta(t){
    const map = {
      text:     {short:'TXT',  long:'Texto',                    cls:'qtype-text'},
      integer:  {short:'INT',  long:'Número entero',            cls:'qtype-integer'},
      decimal:  {short:'DEC',  long:'Número decimal',           cls:'qtype-decimal'},
      single:   {short:'ÚN',   long:'Opciones (selección única)', cls:'qtype-single'},
      multiple: {short:'MULT', long:'Opciones (selección múltiple)', cls:'qtype-multiple'},
      rating:   {short:'★',    long:'Calificación',             cls:'qtype-rating'},
      none:     {short:'—',    long:'Sin respuesta',            cls:'qtype-none'},
      dropdown: {short:'▼',    long:'Lista desplegable',        cls:'qtype-dropdown'},
    };
    return map[t] || {short:t || '?', long:'Tipo desconocido', cls:'qtype-none'};
  }

  // ---------- MODAL: helpers (usar SIEMPRE Bootstrap) ----------
  function getModal() {
    if (!window.bootstrap?.Modal) {
      console.error('Bootstrap Modal no está disponible. Asegura cargar bootstrap.bundle.min.js');
      return null;
    }
    return bootstrap.Modal.getOrCreateInstance(modalEl, {
      backdrop: true,
      focus: true,
      keyboard: true
    });
  }

  function showModal() {
    const m = getModal();
    if (!m) return;
    modalEl.removeAttribute('inert');
    modalEl.removeAttribute('aria-hidden');
    m.show();
  }

  function hideModal() {
    const m = getModal();
    if (!m) return;
    m.hide();
  }

  // Limpia estado/UI al cerrar
  modalEl.addEventListener('hidden.bs.modal', () => {
    CURRENT_QID = null;
    if (optsList) optsList.innerHTML = '';
  });

  function toggleOptionsByType(type) { optsWrap?.classList.toggle('d-none', !optTypes.has(type)); }
  function highlightType(type) {
    if (!typeList) return;
    typeList.querySelectorAll('.list-group-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.type === type);
    });
    toggleOptionsByType(type);
  }
  function readActiveType() {
    const active = typeList?.querySelector('.list-group-item.active');
    return active?.dataset.type || 'single';
  }
  function renderOptionsEditor(q) {
    if (!optsList) return;
    optsList.innerHTML = '';
    const arr = (q.options || []);
    if (!arr.length) arr.push({ label:'Opción 1', correct:false });

    const isSingle = (q.type === 'single');
    const branchingOn = branchAllowed(q.type) && !!qeBranch?.checked;
    ensureBranchShape(q);

    arr.forEach((opt, idx) => {
      const row = document.createElement('div');
      row.className = 'input-group input-group-sm mb-2 align-items-center';
      row.dataset.index = String(idx);
      row.innerHTML = `
        <span class="input-group-text">${idx+1}</span>
        <input type="text" class="form-control" value="${(opt.label ?? '').replaceAll('"','&quot;')}" placeholder="Texto de la opción">
        <div class="input-group-text" style="gap:.35rem">
          <input type="${isSingle ? 'radio' : 'checkbox'}" name="qe-correct" ${opt.correct ? 'checked' : ''} data-opt-correct>
          <small>${isSingle ? 'Correcta' : 'Correcta(s)'}</small>
        </div>
        <select class="form-select form-select-sm w-auto ms-2" data-branch-idx="${idx}" ${branchingOn ? '' : 'disabled'}>
          ${buildBranchOptionsHTML(CURRENT_SEC_ID, q.branch?.byOption?.[idx] ?? null)}
        </select>
        <button type="button" class="btn btn-outline-danger" data-opt-del>&times;</button>
      `;
      if (!branchingOn) {
        row.querySelector('select[data-branch-idx]').classList.add('d-none');
      }
      optsList.appendChild(row);
    });
  }


  optsList?.addEventListener('change', (e) => {
    // A) toggle de "correcta(s)"
    const correct = e.target.closest('[data-opt-correct]');
    if (correct && readActiveType() === 'single' && correct.checked) {
      optsList.querySelectorAll('[data-opt-correct]').forEach(el => {
        if (el !== correct) el.checked = false;
      });
    }

    // B) cambio en el destino de branching
    const sel = e.target.closest('select[data-branch-idx]');
    if (sel && CURRENT_QID) {
      const found = findQuestionById(CURRENT_QID);
      if (!found) return;
      const { q } = found;
      ensureBranchShape(q);
      const idx = Number(sel.dataset.branchIdx);
      const val = sel.value || null; // "" => siguiente
      q.branch.enabled = !!qeBranch?.checked;
      q.branch.byOption[idx] = val;
    }
  });


  function collectOptionsFromUI() {
    if (!optsList) return [];
    const out = [];
    optsList.querySelectorAll('.input-group').forEach(row => {
      const label = row.querySelector('input.form-control')?.value?.trim() || '';
      const correct = !!row.querySelector('[data-opt-correct]')?.checked;
      if (label) out.push({ label, correct });
    });
    return out;
  }

  // Abrir modal haciendo click en q-card (pero no si fue dentro del dropdown)
  document.addEventListener('click', (e) => {
    const card = e.target.closest('.q-card');
    if (!card || e.target.closest('.dropdown')) return;

    const qid = card.dataset.questionId;
    const found = findQuestionById(qid);
    if (!found) return;

    CURRENT_QID = qid;
    const { sec, q } = found;  
    CURRENT_SEC_ID = sec.id;
    ensureOptionsShape(q);      

    if (tInput) tInput.value = (q.title || '').trim();
    if (rChk)   rChk.checked = !!q.required;

    const type = q.type || 'single';
    highlightType(type);
    toggleOptionsByType(type);

    if (optTypes.has(type)) {
      q.options ||= (q.options && Array.isArray(q.options)) ? q.options : ['Opción 1'];
      renderOptionsEditor(q);
    }

      // 🔀 Branch UI
    if (branchAllowed(type)) {
      ensureBranchShape(q);
      qeBranch.disabled = false;
      qeBranch.checked = !!q.branch?.enabled;
    } else {
      qeBranch.checked = false;
      qeBranch.disabled = true;
      delete q.branch;
    }

    showModal();
  });

  // Cambiar tipo dentro del modal
  typeList?.addEventListener('click', (e) => {
    const btn = e.target.closest('.list-group-item[data-type]');
    if (!btn) return;

    const newType = btn.dataset.type;

    // UI: marcar activo y mostrar/ocultar opciones
    typeList.querySelectorAll('.list-group-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    toggleOptionsByType(newType);

    // Actualiza chip en la tarjeta
    if (CURRENT_QID) {
      const card = document.querySelector(`.q-card[data-question-id="${CURRENT_QID}"]`);
      const chip = card?.querySelector('[data-qtype-chip]');
      if (chip) {
        const m = typeMeta(newType);
        chip.textContent = m.short;
        chip.title = m.long;
        chip.className = `qtype-chip ${m.cls}`;
        card.dataset.type = newType;
      }
    }

    // Re-render del editor con el tipo nuevo (para cambiar radio/checkbox al vuelo)
    let vm = { type: newType, options: [{ label:'Opción 1', correct:false }] };
    if (CURRENT_QID) {
      const found = findQuestionById(CURRENT_QID);
      if (found) {
        const { q } = found;
        ensureOptionsShape(q);
        vm = { ...q, type: newType, options: q.options.map(o => ({...o})) };
        if (newType === 'single') {
          const idx = vm.options.findIndex(o => o.correct);
          vm.options = vm.options.map((o,i) => ({ ...o, correct: idx !== -1 && i === idx }));
        }
      }
    }
    renderOptionsEditor(vm);

    // Branching: habilita/inhabilita el switch según el tipo
    qeBranch.disabled = !branchAllowed(newType);
    if (!branchAllowed(newType)) qeBranch.checked = false;
  });

  // Agregar opción
  btnAddOpt?.addEventListener('click', () => {
    const row = document.createElement('div');
    const isSingle = (readActiveType() === 'single');
    row.className = 'input-group input-group-sm mb-2 align-items-center';
    row.innerHTML = `
      <span class="input-group-text">+</span>
      <input type="text" class="form-control" value="" placeholder="Texto de la opción">
      <div class="input-group-text" style="gap:.35rem">
        <input type="${isSingle ? 'radio' : 'checkbox'}" name="qe-correct" data-opt-correct>
        <small>${isSingle ? 'Correcta' : 'Correcta(s)'}</small>
      </div>
      <button type="button" class="btn btn-outline-danger" data-opt-del>&times;</button>
    `;
    optsList?.appendChild(row);
    row.querySelector('input.form-control')?.focus();

    // Si branching está activo, añade el select de destino
    if (branchAllowed(readActiveType()) && qeBranch?.checked) {
      const idx = optsList.querySelectorAll('.input-group').length - 1;
      const sel = document.createElement('select');
      sel.className = 'form-select form-select-sm w-auto ms-2';
      sel.setAttribute('data-branch-idx', String(idx));
      sel.innerHTML = buildBranchOptionsHTML(CURRENT_SEC_ID, null);
      row.insertBefore(sel, row.querySelector('[data-opt-del]'));
    }
  });


  // Eliminar opción
  optsList?.addEventListener('click', (e) => {
    const del = e.target.closest('[data-opt-del]');
    if (!del) return;
    const row = del.closest('.input-group');
    row?.remove();
  });

  // Guardar cambios del modal
  btnSave?.addEventListener('click', () => {
    if (!CURRENT_QID) return hideModal();
    const found = findQuestionById(CURRENT_QID);
    if (!found) return hideModal();

    const { sec, q } = found;
    q.title = (tInput?.value || '').trim() || q.title || 'Pregunta';
    q.required = !!rChk?.checked;

    const newType = readActiveType();
    q.type = newType;

  if (optTypes.has(newType)) {
    let opts = collectOptionsFromUI();
    if (!opts.length) opts = [{ label:'Opción 1', correct:false }];

    if (newType === 'single') {
      const idx = opts.findIndex(o => o.correct);
      opts = opts.map((o,i) => ({ ...o, correct: i === idx && idx !== -1 }));
    }
    q.options = opts;

    // 🔀 Guardar branching
    if (branchAllowed(newType) && qeBranch?.checked) {
      // recolecta selects visibles
      const by = {};
      optsList?.querySelectorAll('select[data-branch-idx]').forEach(sel => {
        const i = Number(sel.dataset.branchIdx);
        const v = sel.value || null; // "" => siguiente
        if (v) by[i] = v;            // guarda solo si hay destino explícito
      });
      q.branch = { enabled: true, byOption: by };
    } else {
      delete q.branch;
    }

  } else {
    delete q.options;
    delete q.branch;
  }


    saveDraft(state);
    rerenderSection(sec.id);
    focusOutsideModal();
    hideModal();
    setTimeout(() => {
      const card = document.querySelector(`.q-card[data-question-id="${q.id}"]`);
      if (card) {
        card.classList.add('ring');
        card.style.outline = '2px solid var(--bs-primary)';
        setTimeout(() => { card.style.outline = ''; card.classList.remove('ring'); }, 1200);
      }
    }, 50);
  });


  // ---------- INIT ----------
  renderAll();

  // debug opcional
  window.__surveyDraft = {
    get: () => JSON.parse(localStorage.getItem(KEY)),
    set: (s) => { state = normalize(s); saveDraft(state); renderAll(); },
    clear: () => { localStorage.removeItem(KEY); state = loadDraft(); renderAll(); }
  };

  function ensureBranchShape(q) {
    // Solo aplica para tipos con branching por opción
    const allowed = new Set(['single', 'dropdown']);
    if (!allowed.has(q.type)) { delete q.branch; return; }

    const byOpt = (q.branch?.byOption && typeof q.branch.byOption === 'object') ? q.branch.byOption : {};
    q.branch = {
      enabled: !!q.branch?.enabled,
      byOption: byOpt   // { [index:number]: sectionId|string|null }
    };
  }

  qeBranch?.addEventListener('change', () => {
    const allow = branchAllowed(readActiveType());
    const on = allow && !!qeBranch.checked;
    // Mostrar/ocultar todos los selects
    optsList?.querySelectorAll('select[data-branch-idx]').forEach(sel => {
      sel.toggleAttribute('disabled', !on);
      sel.classList.toggle('d-none', !on);
    });
  });

  // answersByQuestion: { [qid]: índice seleccionado o valor }
  function nextSectionIdAfter(sec, answersByQuestion){
    // 1) Busca la primera pregunta con branching que aplique
    for (const q of (sec.questions || [])){
      if (q?.branch?.enabled && branchAllowed(q.type)) {
        const ansIdx = answersByQuestion?.[q.id]; // asumiendo índice de opción
        if (ansIdx != null) {
          const target = q.branch.byOption?.[ansIdx] ?? null;
          if (target === 'submit') return 'submit';
          if (target) return target;
        }
      }
    }
    // 2) Si no hubo branch, usa el "Después de la sección"
    if (sec.go_to === 'submit') return 'submit';
    if (sec.go_to) return sec.go_to;

    // 3) Siguiente por orden
    const ordered = [...state.sections].sort((a,b)=>a.order-b.order);
    const idx = ordered.findIndex(s => s.id === sec.id);
    const next = ordered[idx+1];
    return next ? next.id : 'submit';
  }

})();