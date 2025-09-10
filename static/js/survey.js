(function(){
  // --- contador simple para IDs de secciones/preguntas (solo UI)
  let sectionSeq = 1;
  const sectionsStrip = document.getElementById('sectionsStrip');
  const newSectionCol = document.getElementById('newSectionCol');
  const btnNewSection = document.getElementById('btnNewSection');

  function createSectionEl(idx){
    const col = document.createElement('div');
    col.className = 'section-col';
    col.innerHTML = `
      <div class="section-card">
        <div class="section-head">
          <span>Sección ${idx}</span>
          <div class="section-actions">
            <button class="btn btn-sm btn-outline-secondary" title="Renombrar">✎</button>
            <button class="btn btn-sm btn-outline-secondary" title="Más">⋮</button>
          </div>
        </div>
        <div id="qList-${idx}"></div>
        <div class="px-3 pb-2">
          <a class="link-add" data-add-question data-section="${idx}">Nueva pregunta</a>
        </div>
        <div class="section-foot">
          <div class="d-flex align-items-center gap-2">
            <span>Después de la sección ${idx}</span>
            <select class="form-select form-select-sm w-auto">
              <option>Ir a la siguiente sección</option>
              <option>Finalizar encuesta</option>
            </select>
          </div>
        </div>
      </div>`;
    return col;
  }

  function addSection(){
    sectionSeq += 1;
    const col = createSectionEl(sectionSeq);
    sectionsStrip.insertBefore(col, newSectionCol);      // aparece a la derecha
    col.scrollIntoView({behavior:'smooth', inline:'end'}); // desplazamos el strip
  }

  function addQuestion(sectionId){
    const list = document.getElementById(`qList-${sectionId}`);
    if (!list) return;
    const qCount = list.querySelectorAll('.q-card').length + 1;
    const node = document.createElement('div');
    node.className = 'q-card';
    node.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <div class="q-title">Pregunta ${qCount}</div>
        <div class="q-actions">
          <button class="btn btn-sm btn-outline-secondary" title="Requerida">✱</button>
          <button class="btn btn-sm btn-outline-secondary" title="Tipo">◌</button>
        </div>
      </div>
      <div class="form-check mt-1">
        <input class="form-check-input" type="radio" disabled>
        <label class="form-check-label">Opción 1</label>
      </div>
      <div class="q-footer"></div>
    `;
    list.appendChild(node);
    node.scrollIntoView({behavior:'smooth', block:'end'});
  }

  // Botón "Nueva sección"
  btnNewSection?.addEventListener('click', addSection);

  // Delegación para "Nueva pregunta"
  document.addEventListener('click', (e)=>{
    const a = e.target.closest('[data-add-question]');
    if (!a) return;
    e.preventDefault();
    const sid = a.getAttribute('data-section');
    addQuestion(sid);
  });
})();