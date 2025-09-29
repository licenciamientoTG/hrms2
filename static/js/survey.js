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
    s.active  = !!s.active;
    s.lastSeq ||= {section:0,question:0};
    s.sections ||= [];
    const optTypes = new Set(['single','multiple']);
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

  // --- helpers para leer los <script type="application/json"> del template ---
  function readScriptJSON(id){
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || ''); } catch { return null; }
  }

  // Carga el estado inicial del builder
  function loadDraft() {
    // 0) Si hay draft local para este ID, úsalo
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return normalize(JSON.parse(raw));
    } catch {}

    // 1) Si el servidor inyectó JSON (editar), úsalo y siembra settings/audience/título
    const serverDraft =
      readScriptJSON('builder-data') ||                // nuevo id del template
      readScriptJSON('builderPreload');                // compat. con nombre viejo

    if (serverDraft) {
      const seed = normalize(serverDraft);
      saveDraft(seed);

      const sid = SURVEY_ID;
      const settings = readScriptJSON('settings-data')  || readScriptJSON('settingsPreload') || {};
      const audience = readScriptJSON('audience-data')  || readScriptJSON('audiencePreload') || {};
      const titleText = (document.querySelector('#titleView .title-text')?.textContent || 'Encuesta sin título').trim();

      localStorage.setItem(`survey:${sid}:settings`, JSON.stringify(settings));
      localStorage.setItem(`survey:${sid}:audience`, JSON.stringify(audience));
      localStorage.setItem(`survey:${sid}:title`,    titleText);
      return seed;
    }

    // 2) Si NO es “new”, intenta reconstruir desde el DOM del servidor
    if (SURVEY_ID !== 'new') {
      const fromDom = buildStateFromServerDOM();
      if (fromDom) { saveDraft(fromDom); return fromDom; }
      return normalize({ version:1, lastSeq:{section:0,question:0}, sections:[] });
    }

    // 3) NUEVA encuesta: esqueleto por defecto
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
          options: [{ label: 'Opción 1', correct: false }]
        }]
      }]
    };
    saveDraft(init);
    return init;
  }

// Convierte lo que venía renderizado por Django en estado del builder
function buildStateFromServerDOM(){
  const strip = document.getElementById('sectionsStrip');
  if (!strip) return null;

  const secs = [...strip.querySelectorAll('.section-col[data-section-id]')];
  if (!secs.length) return null;

  let qseq = 0;
  const sections = secs.map((col, idx) => {
    const secId = `s${idx+1}`;
    const title = col.querySelector('[data-bind="sec-title"]')?.textContent?.trim() || `Sección ${idx+1}`;
    const qCards = [...col.querySelectorAll('.q-card[data-question-id]')];
    const questions = qCards.map((card, j) => {
      qseq += 1;
      const qTitle = card.querySelector('[data-bind="q-title"], .q-title')?.textContent?.trim() || `Pregunta ${j+1}`;
      const type = card.dataset.type || 'single';
      const required = (card.dataset.required === 'true');
      const opts = [];
      if (type === 'single' || type === 'multiple') {
        card.querySelectorAll('[data-preview] .form-check-label').forEach((lab, k) => {
          const row = lab.closest('.form-check');
          const checked = !!row?.querySelector('.correct-preview:checked');
          opts.push({ label: lab.textContent.trim() || `Opción ${k+1}`, correct: !!checked });
        });
      }
      const q = { id:`q${qseq}`, title:qTitle, type, required, order:j+1 };
      if (opts.length) q.options = opts;
      return q;
    });

    return { id: secId, title, order: idx+1, go_to: null, questions };
  });

  return normalize({
    version: 1,
    active: false,
    lastSeq: { section: sections.length, question: qseq },
    sections
  });
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
    const optTypes = new Set(['single', 'multiple', 'assessment', 'frecuency']);
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
  }
  
  // ---- Helpers de activación (solo local) ----
  const statusPill     = document.getElementById('statusPill');

  function hasAtLeastOneQuestion(){
    return (state.sections || []).some(s => (s.questions || []).length > 0);
  }

  function renderSurveyStatus(){
    const on = !!state.active;
    if (statusPill){
      statusPill.textContent = on ? 'Activada' : 'Desactivada';
      statusPill.classList.toggle('on',  on);
      statusPill.classList.toggle('off', !on);
      statusPill.setAttribute('aria-pressed', String(on));
    }
  }

  async function toggleSurveyActive(){
    const currentlyActive = !!state.active;

    if (!currentlyActive && !hasAtLeastOneQuestion()){
      if (window.Swal){
        await Swal.fire({icon:'info', title:'Sin preguntas', text:'Agrega al menos una pregunta para activar la encuesta.'});
      } else { alert('Agrega al menos una pregunta para activar la encuesta.'); }
      return;
    }

    if (window.Swal){
      const {isConfirmed} = await Swal.fire({
        icon: currentlyActive ? 'warning' : 'question',
        title: currentlyActive ? 'Desactivar encuesta' : 'Activar encuesta',
        text:  currentlyActive ? 'Los participantes dejarán de poder responder.' : 'La encuesta quedará disponible para responder.',
        showCancelButton: true,
        confirmButtonText: currentlyActive ? 'Desactivar' : 'Activar',
        cancelButtonText: 'Cancelar'
      });
      if (!isConfirmed) return;
    }

    state.active = !currentlyActive;
    saveDraft(state);
    renderSurveyStatus();
  }

  statusPill?.addEventListener('click', toggleSurveyActive);
  statusPill?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSurveyActive(); }
  });

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

    // --- META en el footer: tipo + obligatoria con tooltips (texto en círculo) ---
    const foot = node.querySelector('.q-footer');
    const m = typeMeta(q.type); // ya lo tienes
    foot.innerHTML = `
      <div class="q-meta">
        <span class="q-ico" data-bs-toggle="tooltip" title="Tipo de respuesta: ${m.long}">
          ${m.short}
        </span>
        ${q.required ? `
          <span class="q-ico req" data-bs-toggle="tooltip" title="Respuesta obligatoria">✱</span>
        ` : ``}
      </div>`;

    return node;
  }

  function refreshTooltips(){
    if (!window.bootstrap?.Tooltip) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
      // evita duplicados
      if (!bootstrap.Tooltip.getInstance(el)) new bootstrap.Tooltip(el);
    });
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
      renderSurveyStatus(); 
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
  const optTypes = new Set(['single', 'multiple']);

  function branchAllowed(type){ return type === 'single'; }

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
      assessment:{short:'ASG', long:'Evaluación',               cls:'qtype-assessment'},
      frecuency: {short:'FREC', long:'Frecuencia',              cls:'qtype-frecuency'},
      none:     {short:'—',    long:'Sin respuesta',            cls:'qtype-none'},
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
  renderSurveyStatus(); 

  // debug opcional
  window.__surveyDraft = {
    get: () => JSON.parse(localStorage.getItem(KEY)),
    set: (s) => { state = normalize(s); saveDraft(state); renderAll(); },
    clear: () => { localStorage.removeItem(KEY); state = loadDraft(); renderAll(); }
  };

  function ensureBranchShape(q) {
    // Solo aplica para tipos con branching por opción
    const allowed = new Set(['single']);
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

})();

// ===== Audiencia / Segmentación (usuarios + filtros) — LIST-GROUP =====
(function () {
  const form = document.getElementById('surveySettingsForm');
  if (!form) return;

  // DOM
  const audAll = document.getElementById('audAll');
  const audSeg = document.getElementById('audSeg');
  const segBlock = document.getElementById('segmentationBlock');
  const reachCount = document.getElementById('reachCount');

  const selectedUsersWrap = document.getElementById('selectedUsers');
  const userInput = document.getElementById('userSearch');
  const userMenu = document.getElementById('userSearchMenu');
  const userSearchUrl = userInput?.dataset.url;

  // TUS NUEVOS LIST-GROUPS (no <select>)
  const listDeps = document.getElementById('fDepartments');
  const listPos  = document.getElementById('fPositions');
  const listLocs = document.getElementById('fLocations');

    // Buscadores (inputs)
  const searchDeps = document.getElementById('searchDeps');
  const searchPos  = document.getElementById('searchPos');
  const searchLocs = document.getElementById('searchLocs');


  // --- AGRUPACIÓN DE POSICIONES POR TÍTULO ---
  let posTitleMap = {};      
  let selectedPosTitles = new Set();  


  const SURVEY_ID = form.dataset.surveyId || 'draft';
  const LS_KEY = `survey:${SURVEY_ID}:audience`;
  const metaUrl = form.dataset.metaUrl;
  const previewUrl = form.dataset.previewUrl;

  // CSRF
  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }
  const csrftoken = getCookie('csrftoken');

  // Estado
  const emptyState = {
    mode: 'all',
    users: [],
    filters: {
      departments: [],
      positions: [],          // (se enviará al backend, lo vamos a sobreescribir)
      positionsTitles: [],    // <<< NUEVO: títulos elegidos en la UI
      locations: []
    }
  };

  function readState(){
    try {
      const s = JSON.parse(localStorage.getItem(LS_KEY)) || {};
      return {
        ...emptyState,
        ...s,
        filters: { ...emptyState.filters, ...(s.filters || {}) }
      };
    } catch {
      return { ...emptyState };
    }
  }

  function writeState(patch){
    const next = { ...readState(), ...patch };
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    return next;
  }
  function writeFilters(patch){
    const s = readState();
    const f = { ...s.filters, ...patch };
    return writeState({ filters: f });
  }

  // Helpers UI
  function setAudienceMode(segmented){
    segBlock.classList.toggle('d-none', !segmented);
    writeState({ mode: segmented ? 'segmented' : 'all' });
    updatePreviewDebounced();
  }

  // ----- LIST-GROUP helpers -----
  function renderListGroup(el, items, selectedIds){
    if (!el) return;
    const sel = new Set((selectedIds||[]).map(String));
    el.innerHTML = '';
    items.forEach(x => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'list-group-item list-group-item-action';
      b.dataset.id = String(x.id);
      b.textContent = x.name || x.title;
      const active = sel.has(String(x.id));
      if (active) b.classList.add('active');
      b.setAttribute('aria-pressed', active ? 'true' : 'false');
      el.appendChild(b);
    });
  }
  function getSelectedFromGroup(el){
    return [...el.querySelectorAll('.list-group-item.active')]
            .map(b => parseInt(b.dataset.id, 10))
            .filter(Number.isFinite);
  }
  function bindGroup(el){
    el?.addEventListener('click', (e) => {
      const btn = e.target.closest('.list-group-item');
      if (!btn) return;
      const active = btn.classList.toggle('active');
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      writeFilters({
        departments: getSelectedFromGroup(listDeps),
        positions:   getSelectedFromGroup(listPos),
        locations:   getSelectedFromGroup(listLocs),
      });
      updatePreviewDebounced();
    });
  }
  bindGroup(listDeps);
  bindGroup(listLocs);

  // Posición: toggle por TÍTULO (agrupado)
  listPos?.addEventListener('click', (e) => {
    const btn = e.target.closest('.list-group-item');
    if (!btn) return;
    const key = btn.dataset.key;
    if (!key) return;

    const active = btn.classList.toggle('active');
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');

    if (active) selectedPosTitles.add(key);
    else selectedPosTitles.delete(key);

    // Persistimos SOLO títulos; los IDs se expanden antes del preview
    const s = readState();
    s.filters.positionsTitles = [...selectedPosTitles];
    s.filters.positions = []; // limpia posibles restos de versiones previas
    localStorage.setItem(LS_KEY, JSON.stringify(s));

    updatePreviewDebounced();
  });

  // ----- Chips usuarios -----
  function chipHtml(item){
    const email = item.email ? ` <small class="text-muted">(${item.email})</small>` : '';
    return `
      <span class="badge bg-light text-dark me-2 mb-2 d-inline-flex align-items-center" data-user-chip data-id="${item.id}">
        <span class="me-2">${item.label}${email}</span>
        <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" data-remove-user="${item.id}" aria-label="Quitar">×</button>
      </span>`;
  }
  function renderUserChips(){
    const s = readState();
    selectedUsersWrap.innerHTML = '';
    (s.__userCache || []).forEach(u => {
      if (s.users.includes(u.id)) selectedUsersWrap.insertAdjacentHTML('beforeend', chipHtml(u));
    });
  }
  function addUser(item){
    const s = readState();
    if (!s.users.includes(item.id)) {
      s.users.push(item.id);
      const cache = s.__userCache ? [...s.__userCache] : [];
      if (!cache.find(c => c.id === item.id)) cache.push(item);
      localStorage.setItem(LS_KEY, JSON.stringify({ ...s, __userCache: cache }));
      renderUserChips();
      updatePreviewDebounced();
    }
  }
  function removeUser(id){
    const s = readState();
    localStorage.setItem(LS_KEY, JSON.stringify({ ...s, users: s.users.filter(u => u !== id) }));
    renderUserChips();
    updatePreviewDebounced();
  }
  selectedUsersWrap?.addEventListener('click', (e) => {
    const rm = e.target.closest('[data-remove-user]'); if (rm) removeUser(parseInt(rm.dataset.removeUser, 10));
  });

  // Búsqueda de usuarios (sin perder foco)
  const toggleBtn = userInput?.parentElement?.querySelector('[data-bs-toggle="dropdown"]');
  const dd = (toggleBtn && window.bootstrap)
    ? bootstrap.Dropdown.getOrCreateInstance(toggleBtn, { autoClose: 'outside' })
    : null;
  toggleBtn?.addEventListener('shown.bs.dropdown', () => { userInput?.focus(); });
  userInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') e.preventDefault(); });

  async function runUserSearch(q){
    if (!userSearchUrl) return [];
    const url = `${userSearchUrl}?q=${encodeURIComponent(q)}&limit=25`;
    const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }});
    if (!resp.ok) return [];
    return await resp.json();
  }
  function openUserMenu(items){
    if (!userMenu) return;
    userMenu.innerHTML = items.length
      ? items.map(it => `
          <li>
            <button type="button" class="dropdown-item d-flex flex-column"
                    data-user-item='${JSON.stringify(it).replace(/'/g,"&apos;")}'>
              <span>${it.label} <small class="text-muted">${it.email||''}</small></span>
              ${it.meta ? `<small class="text-muted">${it.meta}</small>` : ``}
            </button>
          </li>`).join('')
      : `<li><span class="dropdown-item-text text-muted">Sin resultados</span></li>`;

    const expanded = toggleBtn?.getAttribute('aria-expanded') === 'true';
    if (dd && !expanded) { dd.show(); setTimeout(() => userInput?.focus(), 0); }
    else if (!dd) userMenu.classList.add('show');
  }
  const debounce = (fn, ms)=>{ let id; return (...a)=>{ clearTimeout(id); id=setTimeout(()=>fn(...a), ms); }; };

  // Normaliza texto: minúsculas y sin acentos
  function norm(s){
    return (s||'')
      .toString()
      .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
      .toLowerCase();
  }

  // Filtra un list-group ocultando ítems que no coinciden
  function filterListGroup(listEl, query){
    const q = norm(query);
    listEl?.querySelectorAll('.list-group-item').forEach(btn => {
      const txt = norm(btn.textContent);
      const show = !q || txt.includes(q);
      btn.classList.toggle('d-none', !show);
    });
  }

  const onUserType = debounce(async () => {
    const q = (userInput.value || '').trim();
    if (!q) { if (dd) dd.hide(); else userMenu?.classList.remove('show'); userMenu.innerHTML = ''; return; }
    openUserMenu(await runUserSearch(q));
  }, 250);
  userInput?.addEventListener('input', onUserType);
  userMenu?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-user-item]'); if (!btn) return;
    const item = JSON.parse(btn.getAttribute('data-user-item').replaceAll('&apos;', "'"));
    addUser(item);
    if (dd) dd.hide(); else userMenu.classList.remove('show');
    userInput.value = ''; userInput.focus();
  });

  // Filtro en vivo: Departamento y Ubicación
  searchDeps?.addEventListener('input', debounce(() => {
    filterListGroup(listDeps, searchDeps.value);
  }, 150));

  searchLocs?.addEventListener('input', debounce(() => {
    filterListGroup(listLocs, searchLocs.value);
  }, 150));

  // Filtro en vivo: Posición (como está agrupada por título, re-renderizamos)
  searchPos?.addEventListener('input', debounce(() => {
    renderPositionList(searchPos.value);
  }, 150));

  // Cargar catálogos y pintar list-groups (deps/locs normal, pos AGRUPADAS)
  async function loadMeta(){
    if (!metaUrl) return;
    const resp = await fetch(metaUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }});
    if (!resp.ok) return;

    const { departments, positions, locations } = await resp.json();
    const s = readState();

    // Deps y Locs: list-group normal por id
    renderListGroup(listDeps, departments || [], s.filters.departments);
    renderListGroup(listLocs, locations   || [], s.filters.locations);

    // --- AGRUPAR POSICIONES POR TÍTULO (case-insensitive) ---
    posTitleMap = {}; // { key: { title, ids:[] } }
    (positions || []).forEach(p => {
      const t = (p.title || '').trim();
      if (!t) return;
      const key = t.toLowerCase();
      if (!posTitleMap[key]) posTitleMap[key] = { title: t, ids: [] };
      posTitleMap[key].ids.push(p.id);
    });

    // ⚠️ Si BD guardó IDs (filters.positions) pero no títulos, derivamos titles aquí:
    if ((!s.filters.positionsTitles || !s.filters.positionsTitles.length) &&
        s.filters.positions && s.filters.positions.length) {
      const idSet = new Set(s.filters.positions.map(String));
      const titles = new Set();
      (positions || []).forEach(p => {
        if (idSet.has(String(p.id))) {
          const key = (p.title || '').trim().toLowerCase();
          if (key) titles.add(key);
        }
      });
      s.filters.positionsTitles = [...titles];
      localStorage.setItem(LS_KEY, JSON.stringify(s)); // persistimos para que la UI marque bien
    }

    // Restaurar selección en la lista de Posiciones por título
    selectedPosTitles = new Set(s.filters.positionsTitles || []);
    renderPositionList();


    // Restaurar títulos seleccionados y render
    selectedPosTitles = new Set(s.filters.positionsTitles || []);
    renderPositionList();
  }

  function renderPositionList(query=''){
    if (!listPos) return;
    listPos.innerHTML = '';
    const q = norm(query);

    Object.entries(posTitleMap)
      .sort((a,b) => a[1].title.localeCompare(b[1].title))
      .forEach(([key, obj]) => {
        if (q && !norm(obj.title).includes(q)) return; // aplica filtro

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'list-group-item list-group-item-action';
        btn.dataset.key = key;
        btn.textContent = obj.title;

        const active = selectedPosTitles.has(key);
        if (active) btn.classList.add('active');
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');

        listPos.appendChild(btn);
      });
  }

  function expandPositionTitlesToIds(filters){
    const keys = filters.positionsTitles || [];
    return keys.flatMap(k => posTitleMap[k]?.ids || []);
  }

  // Preview
  async function updatePreview(){
    if (!previewUrl) return;
    const s = readState();
    const payload = {
      allUsers: (s.mode === 'all'),
      users: s.users,
      filters: {
        departments: s.filters.departments,
        positions:   expandPositionTitlesToIds(s.filters), 
        locations:   s.filters.locations
      }
    };

    try {
      const resp = await fetch(previewUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      reachCount.textContent = (data && typeof data.count === 'number') ? data.count : '0';
    } catch { reachCount.textContent = '—'; }
  }
  const updatePreviewDebounced = debounce(updatePreview, 150);

  // Radios
  audAll?.addEventListener('change', () => setAudienceMode(false));
  audSeg?.addEventListener('change', () => setAudienceMode(true));

  // Init
  (async function initAudience(){
    const s = readState();
    if (s.mode === 'segmented') { audSeg.checked = true; setAudienceMode(true); }
    else { audAll.checked = true; setAudienceMode(false); }
    await loadMeta();
    renderUserChips();
    updatePreview();
  })();
})();

/* === AJUSTES: Mensaje + Anónima (persistir en localStorage) === */
(function settingsLocal(){
  const form = document.getElementById('surveySettingsForm');
  if (!form) return;

  const SURVEY_ID    = form.dataset.surveyId || 'draft';
  const SETTINGS_KEY = `survey:${SURVEY_ID}:settings`;

  const msgEl  = document.getElementById('autoMessage');
  const anonEl = document.getElementById('isAnonymous');

  // <-- aquí definimos los valores por defecto
  const DEFAULTS = { autoMessage: '', isAnonymous: false };

  function readSettings(){
    try {
      return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {}) };
    } catch {
      return { ...DEFAULTS };
    }
  }
  function writeSettings(patch){
    const next = { ...readSettings(), ...patch };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
    return next;
  }

  // Restaurar al cargar
  const s = readSettings();
  if (msgEl)  msgEl.value    = s.autoMessage;
  if (anonEl) anonEl.checked = !!s.isAnonymous; // quedará false si no hay nada guardado

  // Guardar cambios en caliente
  msgEl ?.addEventListener('input',  () => writeSettings({ autoMessage: msgEl.value }));
  anonEl?.addEventListener('change', () => writeSettings({ isAnonymous: !!anonEl.checked }));
})();

function getCookie(name){
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

function renameLocalStoragePrefix(fromPrefix, toPrefix){
  const keys = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(fromPrefix)) keys.push(k);
  }
  keys.forEach(k => {
    const v = localStorage.getItem(k);
    localStorage.setItem(k.replace(fromPrefix, toPrefix), v);
    localStorage.removeItem(k);
  });
}

(function () {
  const box = document.getElementById('titleBox');
  if (!box) return;

  const view = document.getElementById('titleView');
  const edit = document.getElementById('titleEdit');
  const btnEdit = document.getElementById('titleEditBtn');
  const btnSave = document.getElementById('titleSaveBtn');
  const btnCancel = document.getElementById('titleCancelBtn');
  const input = document.getElementById('surveyTitleInput');
  const viewText = view.querySelector('.title-text');

  const surveyId = box.dataset.surveyId || 'unknown';
  const LS_KEY = `survey:${surveyId}:title`;
  const defaultTitle = box.dataset.defaultTitle || 'Encuesta sin título';

  const qsa = (sel) => Array.from(document.querySelectorAll(sel));

  // Seguridad mínima (evita HTML en el título)
  const sanitize = (s) => (s || '').replace(/<[^>]+>/g, '').trim();

  // Carga inicial desde LS o del DOM
  const stored = sanitize(localStorage.getItem(LS_KEY) || '');
  if (stored) {
    setTitle(stored, { persist:false });
  } else {
    // si viene vacío/placeholder en server, mantenlo
    setTitle(sanitize(viewText.textContent) || defaultTitle, { persist:false });
  }

  // Entrar a modo edición
  btnEdit.addEventListener('click', () => {
    input.value = getTitle();
    toggle(true);
    // foco al final
    requestAnimationFrame(() => {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    });
  });

  // Guardar
  btnSave.addEventListener('click', saveFromInput);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveFromInput();
    if (e.key === 'Escape') cancelEdit();
  });

  // Cancelar
  btnCancel.addEventListener('click', cancelEdit);
  input.addEventListener('blur', () => {
    // guarda al salir del foco (si no deseas esto, comenta esta línea)
    saveFromInput();
  });

  function saveFromInput() {
    const v = sanitize(input.value) || defaultTitle;
    setTitle(v, { persist:true });
    toggle(false);
  }
  function cancelEdit() {
    input.value = getTitle();
    toggle(false);
  }

  function toggle(editMode) {
    edit.hidden = !editMode;
    view.hidden = editMode;
  }

  function getTitle() {
    return sanitize(viewText.textContent) || defaultTitle;
  }

  // Actualiza todos los lugares donde muestres el título
  function setTitle(value, { persist=true } = {}) {
    viewText.textContent = value;
    // cualquier otro lugar que lo consuma (ej. encabezados de secciones)
    qsa('[data-title-target="header"]').forEach(el => el.textContent = value);
    qsa('[data-title-target="section"]').forEach(el => el.textContent = value);
    if (persist) {
      try { localStorage.setItem(LS_KEY, value); } catch(e) {}
    }
  }

  window.addEventListener('beforeunload', () => {
    if (window.__SURVEY_NAVIGATING__) return; // 👈 no re-escribas si cancelo
    try { localStorage.setItem(LS_KEY, getTitle()); } catch(e) {}
  });
})();

function blockSurveyAutosaveWrites() {
  // Evita que cualquier módulo vuelva a escribir survey:* mientras salimos
  const orig = Storage.prototype.setItem;
  if (Storage.prototype.__surveyPatched__) return; // evita doble parche
  Storage.prototype.__surveyPatched__ = true;
  Storage.prototype.setItem = function (k, v) {
    if (window.__SURVEY_NAVIGATING__ && String(k).startsWith('survey:')) return;
    return orig.apply(this, arguments);
  };
}

(function publishHandler(){
  const form = document.getElementById('surveySettingsForm');
  if (!form) return;

  const SURVEY_ID = form.dataset.surveyId || 'new';

  function removeLocalStorageByPrefix(prefix){
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix)) keys.push(k);
    }
    keys.forEach(k => localStorage.removeItem(k));
  }

  function clearAllSurveyKeys(idLike){
    // borra tanto los draft como settings/título/audience
    removeLocalStorageByPrefix(`survey:draft:${idLike}`);
    removeLocalStorageByPrefix(`survey:${idLike}:`);
  }

  async function persistOnServer(){
    const rawId = SURVEY_ID;
    const isNew = (rawId === 'new');

    const builderKey  = `survey:draft:${rawId}`;
    const settingsKey = `survey:${rawId}:settings`;
    const audienceKey = `survey:${rawId}:audience`;
    const titleKey    = `survey:${rawId}:title`;

    const payload = {
      builder:  JSON.parse(localStorage.getItem(builderKey)  || '{}'),
      settings: JSON.parse(localStorage.getItem(settingsKey) || '{}'),
      audience: JSON.parse(localStorage.getItem(audienceKey) || '{}'),
      title:    (localStorage.getItem(titleKey) || '').trim()
    };

    const url = isNew
      ? (form.dataset.importCreateUrl)
      : (form.dataset.importUpdateUrl || `/surveys/${rawId}/import/`);

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(payload)
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) throw new Error('Error al guardar');
    return String(data.id);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btnPublish');
    btn?.setAttribute('disabled', 'disabled');

    try {
      const newId = await persistOnServer();
      window.__SURVEY_NAVIGATING__ = 'publish';
      blockSurveyAutosaveWrites();

      // limpia "new" y también el id real devuelto por el backend
      clearAllSurveyKeys('new');
      clearAllSurveyKeys(newId);

      const backUrl = form.dataset.dashboardUrl || '/surveys/admin/';
      location.replace(backUrl);
    } catch (err) {
      console.error(err);
      alert('Error al guardar');
    } finally {
      btn?.removeAttribute('disabled');
    }
  });
})();

function clearSurveyStorage() {
  // Borra absolutamente todo lo que empiece con "survey:"
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i);
    if (k && k.startsWith('survey:')) localStorage.removeItem(k);
  }
}


document.getElementById("btnCancelSurvey")?.addEventListener("click", function (e) {
  e.preventDefault();

  Swal.fire({
    title: "¿Cancelar encuesta?",
    text: "Se perderán todos los cambios no guardados.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#d33",
    cancelButtonColor: "#6c757d",
    confirmButtonText: "Sí, cancelar",
    cancelButtonText: "Volver"
  }).then((result) => {
    if (!result.isConfirmed) return;

    // Evita que cualquier módulo vuelva a escribir survey:* al salir
    window.__SURVEY_NAVIGATING__ = 'cancel';
    blockSurveyAutosaveWrites();

    // Borra todo lo de survey:*
    clearSurveyStorage();

    // Navega
    location.replace(this.href);
  });
});

(function () {
  // CSRF (usa esto si CSRF_COOKIE_HTTPONLY = False)
  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('a[data-action="delete"]');
    if (!btn) return;

    e.preventDefault();

    // Confirmación
    const ask = window.Swal
      ? await Swal.fire({
          icon: 'warning',
          title: 'Eliminar encuesta',
          text: 'Esta acción no se puede deshacer.',
          showCancelButton: true,
          confirmButtonText: 'Eliminar',
          cancelButtonText: 'Cancelar'
        })
      : { isConfirmed: confirm('¿Eliminar encuesta?') };

    if (!ask.isConfirmed) return;

    const url = btn.dataset.url;
    const row = btn.closest('tr');

    try {
      btn.classList.add('disabled'); // evita doble click

      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCookie('csrftoken')   // <- token de cookie
        }
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) throw new Error('Delete failed');

      // Quitar la fila sin recargar
      if (row) row.remove();

      if (window.Swal) Swal.fire({icon:'success', title:'Eliminada', timer:1200, showConfirmButton:false});
    } catch (err) {
      if (window.Swal) Swal.fire({icon:'error', title:'No se pudo eliminar'});
      else alert('No se pudo eliminar');
    } finally {
      btn.classList.remove('disabled');
    }
  });
})();

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('surveySearchInput');
  if (!input) return;

  const lists = [
    document.getElementById('list-available'),
    document.getElementById('list-completed')
  ].filter(Boolean);

  // normaliza: minúsculas y sin acentos
  const norm = s => (s||'')
    .toString()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().trim();

  function getPlaceholderRow(ul){
    // Reutiliza el placeholder existente (el <li> sin data-status) o crea uno
    let row = ul.querySelector('.survey-item:not([data-status])');
    if (!row) {
      row = document.createElement('li');
      row.className = 'survey-item';
      row.innerHTML = `
        <div class="left">
          <span class="title" style="font-weight:500;color:#6b7280;"></span>
        </div>`;
      ul.appendChild(row);
    }
    return row;
  }

  function applyFilter(){
    const q = norm(input.value);

    lists.forEach(ul => {
      const items = [...ul.querySelectorAll('.survey-item[data-status]')]; // solo encuestas reales
      const placeholder = getPlaceholderRow(ul);

      let visible = 0;
      items.forEach(li => {
        const title = li.dataset.title || li.querySelector('.title')?.textContent || '';
        const ok = !q || norm(title).includes(q);
        li.hidden = !ok;
        if (ok) visible++;
      });

      // Mensaje según haya resultados o no
      const msgEl = placeholder.querySelector('.title');
      if (visible === 0) {
        msgEl.textContent = q ? `No hay resultados para “${input.value}”.` : `No tienes encuestas disponibles.`;
        placeholder.hidden = false;
      } else {
        placeholder.hidden = true;
      }
    });
  }

  // filtra mientras escribes; Esc borra
  input.addEventListener('input', applyFilter);
  input.addEventListener('keydown', e => { if (e.key === 'Escape'){ input.value=''; applyFilter(); }});

  applyFilter(); // estado inicial
});

// Al final del archivo survey.js, REEMPLAZA esta función:

(function(){
  const $ = (sel, ctx=document)=>ctx.querySelector(sel);
  const $$ = (sel, ctx=document)=>Array.from(ctx.querySelectorAll(sel));

  const avail = $('#list-available');
  const done  = $('#list-completed');
  if(!avail || !done) return;

  function realItems(list){
    return $$('.survey-item:not([data-empty])', list);
  }

  function ensureEmptyState(){
    // Disponibles
    const availHas = realItems(avail).length > 0;
    const availEmpty = $('.survey-item[data-empty]', avail);
    if(availEmpty) availEmpty.style.display = availHas ? 'none' : '';

    // Completados
    const doneHas = realItems(done).length > 0;
    const doneEmpty = $('.survey-item[data-empty]', done);
    if(doneEmpty) doneEmpty.style.display = doneHas ? 'none' : '';
  }

  ensureEmptyState();

  // 2) Tabs
  $$('.surveys-tabs .tab').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      $$('.surveys-tabs .tab').forEach(b=>{
        b.classList.toggle('active', b === btn);
        b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
      });
      const target = btn.dataset.target; // "available" | "completed"
      $('#list-available').classList.toggle('is-hidden', target !== 'available');
      $('#list-completed').classList.toggle('is-hidden', target !== 'completed');
    });
  });

  // 3) Búsqueda (filtra en ambas listas)
  const search = $('#surveySearchInput');
  if(search){
    search.addEventListener('input', ()=>{
      const q = search.value.trim().toLowerCase();
      [avail, done].forEach(list=>{
        realItems(list).forEach(li=>{
          const text = (li.dataset.title||'').toLowerCase();
          li.style.display = text.includes(q) ? '' : 'none';
        });
      });
    });
  }
})();