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
      (q.options || [{label:'Opción 1', correct:false}]).slice(0, 3).forEach((opt, i) => {
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
      (q.options || [{label:'Opción 1', correct:false}]).slice(0, 3).forEach((opt, i) => {
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
      options:['Opción 1']
    };
    (sec.questions ||= []).push(q);

    saveDraft(state);
    rerenderSection(sec.id);
  }

  function renameSection(sectionId){
    const sec = state.sections.find(s => s.id === sectionId);
    if (!sec) return;
    const v = prompt('Nombre de la sección', sec.title || `Sección ${sec.order}`);
    if (v == null) return;
    sec.title = v.trim();
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

  let CURRENT_QID = null;
  const optTypes = new Set(['single', 'multiple', 'dropdown']);

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
        <button type="button" class="btn btn-outline-danger" data-opt-del>&times;</button>
      `;
      optsList.appendChild(row);
    });
  }

  optsList?.addEventListener('change', (e) => {
    const input = e.target.closest('[data-opt-correct]');
    if (!input) return;
    const isSingle = (readActiveType() === 'single');
    if (isSingle && input.checked) {
      // Desmarca todos los demás radios
      optsList.querySelectorAll('[data-opt-correct]').forEach(el => {
        if (el !== input) el.checked = false;
      });
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
    const { q } = found;

    if (tInput) tInput.value = (q.title || '').trim();
    if (rChk)   rChk.checked = !!q.required;

    const type = q.type || 'single';
    highlightType(type);
    toggleOptionsByType(type);

    if (optTypes.has(type)) {
      q.options ||= (q.options && Array.isArray(q.options)) ? q.options : ['Opción 1'];
      renderOptionsEditor(q);
    }

    showModal();
  });

  // Cambiar tipo dentro del modal
  typeList?.addEventListener('click', (e) => {
    const btn = e.target.closest('.list-group-item[data-type]');
    if (!btn) return;
    typeList.querySelectorAll('.list-group-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    toggleOptionsByType(btn.dataset.type);

    if (optTypes.has(btn.dataset.type)) {
      if (CURRENT_QID) {
        const found = findQuestionById(CURRENT_QID);
        if (found) {
          const { q } = found;
          ensureOptionsShape(q);
          // Si cambia a single, fuerza solo 1 correcta
          if (btn.dataset.type === 'single') {
            const firstIdx = q.options.findIndex(o => o.correct);
            q.options.forEach((o, i) => { o.correct = (i === (firstIdx === -1 ? 0 : firstIdx)); });
          }
          renderOptionsEditor(q);
        }
      } else {
        renderOptionsEditor({ type: btn.dataset.type, options: [{ label:'Opción 1', correct:false }] });
      }
    }
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
      // Enforcement final: si es single, garantiza 0..1 marcada
      if (newType === 'single') {
        const idx = opts.findIndex(o => o.correct);
        opts = opts.map((o,i) => ({ ...o, correct: i === idx && idx !== -1 }));
      }
      q.options = opts;
    } else {
      delete q.options;
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
})();