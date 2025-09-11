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
        questions: [{ id: 'q1', title: 'Pregunta 1', type: 'single', required: false, order: 1 }]
      }]
    };
    saveDraft(init);
    return init;
  }
  function saveDraft(s){ localStorage.setItem(KEY, JSON.stringify(s)); }
  function normalize(s){ s.version ||= 1; s.lastSeq ||= {section:0,question:0}; s.sections ||= []; return s; }

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
    const frag = tplQuestion.content.cloneNode(true);
    const node = frag.querySelector('.q-card');

    node.dataset.questionId = q.id;

    const titleEl = node.querySelector('[data-bind="q-title"]');
    titleEl.textContent = q.title || 'Pregunta';

    // set id en acciones
    node.querySelectorAll('[data-action="q.rename"]').forEach(b => b.dataset.id = q.id);
    node.querySelectorAll('[data-action="q.delete"]').forEach(b => b.dataset.id = q.id);

    return node;
  }

  // ---------- RENDER ----------
  function renderAll(){
    // quita todo menos "nueva sección"
    [...strip.querySelectorAll('.section-col')].forEach(c => { if (c !== newSectionCol) c.remove(); });

    const sections = [...state.sections].sort((a,b)=>a.order-b.order);
    sections.forEach(sec => {
      const col = cloneSection(sec);

      // preguntas
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

    (sec.questions ||= []).push({
      id:`q${nextQ}`, title:`Pregunta ${order}`, type:'single', required:false, order
    });
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

  function renameQuestion(questionId){
    const sec = state.sections.find(s => (s.questions||[]).some(q => q.id === questionId));
    if (!sec) return;
    const q = sec.questions.find(x => x.id === questionId);
    const v = prompt('Título de la pregunta', q.title || 'Pregunta');
    if (v == null) return;
    q.title = v.trim();
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
    // limpia jumps que apuntaban a la sección borrada
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

  // ---------- EVENTS ----------
  btnNewSection?.addEventListener('click', addSection);

  document.addEventListener('click', (e) => {
    const add = e.target.closest('[data-add-question]');
    if (add) { e.preventDefault(); return addQuestion(add.dataset.section); }

    const item = e.target.closest('.dropdown-item');
    if (!item) return;

    if (item.dataset.action === 'sec.rename') return renameSection(item.dataset.id);
    if (item.dataset.action === 'q.rename')   return renameQuestion(item.dataset.id);
    if (item.dataset.action === 'sec.delete') return deleteSectionById(item.dataset.id || item.closest('.section-col')?.dataset.sectionId);
    if (item.dataset.action === 'q.delete')   return deleteQuestionById(item.dataset.id || item.closest('.q-card')?.dataset.questionId);
  });

  // show menú jump (lazy)
  document.addEventListener('show.bs.dropdown', (e) => {
    const btn = e.target.closest('[data-section-jump]');
    if (!btn) return;
    const sid = btn.dataset.section;
    const ul  = btn.parentElement.querySelector('[data-jump-menu]');
    buildJumpMenu(ul, sid);
  });

  // pick opción jump
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

  // ---------- INIT ----------
  renderAll();

  // debug opcional
  window.__surveyDraft = {
    get: () => JSON.parse(localStorage.getItem(KEY)),
    set: (s) => { state = normalize(s); saveDraft(state); renderAll(); },
    clear: () => { localStorage.removeItem(KEY); state = loadDraft(); renderAll(); }
  };
})();
