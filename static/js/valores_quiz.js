(() => {
  const root = document.querySelector(".page.valores-quiz");
  if (!root) return;

  const form = document.getElementById("quizForm");
  const btnSubmit = document.getElementById("btnSubmit");
  const box = document.getElementById("resultBox");

  const submitUrl = root.getAttribute("data-submit-url") || "";
  const finalizeUrl = root.getAttribute("data-finalize-url") || "";
  const coursesUrl = root.getAttribute("data-courses-url") || "";

  const tokenInput = form ? form.querySelector('input[name="csrfmiddlewaretoken"]') : null;
  const csrfToken = tokenInput ? tokenInput.value : "";

  const modalEl = document.getElementById("quizResultModal");
  const btnTryAgain = document.getElementById("btnTryAgain");
  const btnTry100 = document.getElementById("btnTry100");
  const btnFinishCourse = document.getElementById("btnFinishCourse");
  const btnQuizClose = document.getElementById("btnQuizClose");

  const quizTitle = document.getElementById("quizTitle");
  const quizSubtitle = document.getElementById("quizSubtitle");
  const quizScoreLabel = document.getElementById("quizScoreLabel");
  const quizPctLabel = document.getElementById("quizPctLabel");
  const quizMinLabel = document.getElementById("quizMinLabel");
  const quizStateLabel = document.getElementById("quizStateLabel");
  const quizFootnote = document.getElementById("quizFootnote");
  const quizReview = document.getElementById("quizReview");

  const quizIconOk = document.getElementById("quizIconOk");
  const quizIconBad = document.getElementById("quizIconBad");

  const confettiCanvas = document.getElementById("quizConfetti");

  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const btnShowAll = document.getElementById("btnShowAll");
  const progressBar = document.getElementById("quizProgressBar");
  const progressText = document.getElementById("quizProgressText");

  if (!form || !btnSubmit || !box || !modalEl) return;

  const questions = Array.from(document.querySelectorAll(".valores-quiz .q"));
  const totalQ = questions.length;
  if (!totalQ) return;

  let currentQ = 0;
  let showAll = false;

  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));

  function isMultipleQuestion(qEl) {
    return !!qEl.querySelector('input[type="checkbox"]');
  }

  function isQuestionAnswered(qEl) {
    if (!qEl) return false;
    if (isMultipleQuestion(qEl)) {
      return !!qEl.querySelector('input[type="checkbox"]:checked');
    }
    return !!qEl.querySelector('input[type="radio"]:checked');
  }

  function answeredCount() {
    return questions.filter(isQuestionAnswered).length;
  }

  function syncSelectedClasses(qEl) {
    if (!qEl) return;
    qEl.querySelectorAll(".opt").forEach((label) => {
      const input = label.querySelector("input");
      label.classList.toggle("is-selected", !!(input && input.checked));
    });
  }

  function syncAllSelectedClasses() {
    questions.forEach(syncSelectedClasses);
  }

  function clearMarks() {
    document.querySelectorAll(".valores-quiz .opt").forEach((el) => {
      el.classList.remove("is-correct", "is-wrong");
    });
    document.querySelectorAll(".valores-quiz .q").forEach((el) => {
      el.classList.remove("is-correct", "is-wrong");
    });
  }

  function disableForm() {
    form.querySelectorAll("input").forEach((i) => {
      i.disabled = true;
    });
    btnSubmit.disabled = true;
    if (btnPrev) btnPrev.disabled = true;
    if (btnNext) btnNext.disabled = true;
    if (btnShowAll) btnShowAll.disabled = true;
  }

  function enableForm(clearSelections) {
    form.querySelectorAll("input").forEach((i) => {
      i.disabled = false;
    });
    btnSubmit.disabled = false;
    if (btnShowAll) btnShowAll.disabled = false;

    if (clearSelections) {
      form.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((input) => {
        input.checked = false;
      });
      syncAllSelectedClasses();
    }
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatScore(value) {
    const n = typeof value === "number" ? value : Number(value || 0);
    if (!Number.isFinite(n)) return "0";
    const rounded = Math.round(n * 100) / 100;
    if (Number.isInteger(rounded)) return String(rounded);
    return rounded.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  }

  function renderReview(details) {
    if (!quizReview) return;

    if (!Array.isArray(details) || !details.length) {
      quizReview.style.display = "none";
      quizReview.innerHTML = "";
      return;
    }

    const rows = details
      .map((d) => {
        const selectedText = Array.isArray(d.selected_option_texts) && d.selected_option_texts.length
          ? d.selected_option_texts.join(", ")
          : "Sin respuesta";

        const correctText = Array.isArray(d.correct_option_texts) && d.correct_option_texts.length
          ? d.correct_option_texts.join(", ")
          : "No disponible";

        const earnedPoints = typeof d.earned_points === "number" ? d.earned_points : 0;
        const badge = d.is_correct
          ? '<span class="badge bg-success">Correcta</span>'
          : (d.is_partial
            ? '<span class="badge bg-warning text-dark">Parcial</span>'
            : '<span class="badge bg-danger">Incorrecta</span>');

        return (
          '<div class="review-item">' +
            '<div class="d-flex justify-content-between align-items-center gap-2 mb-1">' +
              '<strong>' + escapeHtml(d.question_text || "Pregunta") + '</strong>' +
              badge +
            "</div>" +
            '<div class="small text-muted"><strong>Tu respuesta:</strong> ' + escapeHtml(selectedText) + "</div>" +
            '<div class="small"><strong>Respuesta correcta:</strong> ' + escapeHtml(correctText) + "</div>" +
            '<div class="small"><strong>Puntaje:</strong> ' + escapeHtml(formatScore(earnedPoints)) + " / 1</div>" +
          "</div>"
        );
      })
      .join("");

    quizReview.innerHTML = '<h6 class="fw-bold mb-2">Revisión de respuestas</h6>' + rows;
    quizReview.style.display = "block";
  }

  function markAnswers(details) {
    if (!Array.isArray(details)) return;

    details.forEach((d) => {
      const questionId = d.question_id;
      if (!questionId) return;

      const qEl = document.querySelector('.valores-quiz .q[data-qid="' + questionId + '"]');
      if (!qEl) return;

      const selected = new Set(Array.isArray(d.selected_option_ids) ? d.selected_option_ids : []);
      const correct = new Set(Array.isArray(d.correct_option_ids) ? d.correct_option_ids : []);

      const isPartial = !!d.is_partial;

      qEl.classList.toggle("is-correct", !!d.is_correct);
      qEl.classList.toggle("is-partial", isPartial);
      qEl.classList.toggle("is-wrong", !d.is_correct && !isPartial);

      qEl.querySelectorAll(".opt[data-optid]").forEach((label) => {
        const oid = label.getAttribute("data-optid") || "";
        if (correct.has(oid)) label.classList.add("is-correct");
        if (selected.has(oid) && !correct.has(oid)) label.classList.add("is-wrong");
      });
    });
  }

  let modalInstance = null;

  function showModal() {
    if (window.bootstrap && window.bootstrap.Modal) {
      modalInstance = modalInstance || new window.bootstrap.Modal(modalEl);
      modalInstance.show();
      return;
    }
    if (window.jQuery && window.jQuery(modalEl).modal) {
      window.jQuery(modalEl).modal("show");
      return;
    }
    modalEl.style.display = "block";
    modalEl.classList.add("show");
  }

  function hideModal() {
    if (modalInstance && modalInstance.hide) {
      modalInstance.hide();
      return;
    }
    if (window.jQuery && window.jQuery(modalEl).modal) {
      window.jQuery(modalEl).modal("hide");
      return;
    }
    modalEl.style.display = "none";
    modalEl.classList.remove("show");
  }

  function startConfetti(ms) {
    if (!confettiCanvas) return;

    const ctx = confettiCanvas.getContext("2d");
    if (!ctx) return;

    confettiCanvas.style.display = "block";
    confettiCanvas.width = window.innerWidth;
    confettiCanvas.height = window.innerHeight;

    const palette = ["#014AA9", "#9DC72E", "#009558", "#009CDF", "#ffffff"];
    const pieces = [];
    const n = 140;

    for (let i = 0; i < n; i++) {
      pieces.push({
        x: Math.random() * confettiCanvas.width,
        y: -20 - Math.random() * confettiCanvas.height * 0.2,
        w: 6 + Math.random() * 8,
        h: 8 + Math.random() * 12,
        vx: -1 + Math.random() * 2,
        vy: 2 + Math.random() * 4,
        r: Math.random() * Math.PI,
        vr: -0.1 + Math.random() * 0.2,
        color: palette[Math.floor(Math.random() * palette.length)],
      });
    }

    const start = performance.now();

    function frame(t) {
      const elapsed = t - start;
      ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);

      pieces.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.r += p.vr;

        if (p.y > confettiCanvas.height + 40) {
          p.y = -30;
          p.x = Math.random() * confettiCanvas.width;
        }

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.r);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      });

      if (elapsed < ms) {
        requestAnimationFrame(frame);
      } else {
        confettiCanvas.style.display = "none";
        ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
      }
    }

    requestAnimationFrame(frame);
  }

  function openResultModal(payload) {
    const score = typeof payload.score === "number" ? payload.score : 0;
    const total = typeof payload.total_questions === "number" ? payload.total_questions : 0;
    const pct = typeof payload.percentage_score === "number" ? payload.percentage_score : 0;
    const passed = !!payload.passed;
    const minLabel = (payload && payload.min_to_finish_label) ? payload.min_to_finish_label : "10/12";

    quizMinLabel.textContent = minLabel;
    quizScoreLabel.textContent = formatScore(score) + "/" + total;
    quizPctLabel.textContent = Math.round(pct) + "%";

    renderReview(payload && payload.details ? payload.details : []);

    if (passed) {
      quizTitle.textContent = "Listo para finalizar";
      quizSubtitle.textContent =
        "Alcanzaste el mínimo aprobatorio (" + minLabel + "). Puedes finalizar o intentar conseguir el 100%.";
      quizStateLabel.textContent = "Aprobado";

      quizIconOk.style.display = "inline-block";
      quizIconBad.style.display = "none";

      btnFinishCourse.style.display = "inline-flex";
      btnTry100.style.display = "inline-flex";

      quizFootnote.textContent =
        "Si intentas el 100%, puedes repetir el cuestionario. El curso solo se marca como completado cuando presionas Finalizar curso.";

      startConfetti(2000);
    } else {
      quizTitle.textContent = "Vuelve a intentarlo";
      quizSubtitle.textContent =
        "No alcanzaste el mínimo aprobatorio (" + minLabel + "). Necesitas volver a intentarlo para poder finalizar.";
      quizStateLabel.textContent = "No aprobado";

      quizIconOk.style.display = "none";
      quizIconBad.style.display = "inline-block";

      btnFinishCourse.style.display = "none";
      btnTry100.style.display = "none";

      quizFootnote.textContent = "Tip: revisa la sección de revisión antes de reintentar.";
    }

    showModal();
  }

  function setVisible() {
    questions.forEach((qEl, idx) => {
      qEl.style.display = showAll || idx === currentQ ? "block" : "none";
    });
  }

  function updateStepperUI() {
    const a = answeredCount();
    const pct = totalQ ? Math.round((a / totalQ) * 100) : 0;

    if (progressBar) progressBar.style.width = pct + "%";

    if (progressText) {
      progressText.textContent = showAll
        ? "Respondidas " + a + "/" + totalQ
        : "Pregunta " + (currentQ + 1) + " de " + totalQ + " | Respondidas " + a + "/" + totalQ;
    }

    if (btnPrev) btnPrev.disabled = currentQ === 0;
    if (btnNext) btnNext.disabled = !isQuestionAnswered(questions[currentQ]);

    btnSubmit.style.display = showAll || currentQ === totalQ - 1 ? "inline-flex" : "none";
    btnSubmit.disabled = a !== totalQ;

    if (btnNext) btnNext.style.display = !showAll && currentQ < totalQ - 1 ? "inline-flex" : "none";
    if (btnPrev) btnPrev.style.display = showAll ? "none" : "inline-flex";
    if (btnShowAll) btnShowAll.textContent = showAll ? "Modo paso a paso" : "Ver todas";
  }

  function goTo(i) {
    currentQ = clamp(i, 0, totalQ - 1);
    setVisible();
    updateStepperUI();

    const qEl = questions[currentQ];
    if (qEl) qEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resetStepper() {
    showAll = false;
    currentQ = 0;
    setVisible();
    updateStepperUI();
  }

  questions.forEach((qEl) => {
    qEl.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        syncSelectedClasses(qEl);
        updateStepperUI();
      });
    });
  });

  syncAllSelectedClasses();
  setVisible();
  updateStepperUI();

  if (btnPrev) btnPrev.addEventListener("click", () => goTo(currentQ - 1));
  if (btnNext) {
    btnNext.addEventListener("click", () => {
      if (!isQuestionAnswered(questions[currentQ])) return;
      goTo(currentQ + 1);
    });
  }

  if (btnShowAll) {
    btnShowAll.addEventListener("click", () => {
      showAll = !showAll;
      setVisible();
      updateStepperUI();
    });
  }

  if (btnQuizClose) btnQuizClose.addEventListener("click", () => hideModal());

  if (btnTryAgain) {
    btnTryAgain.addEventListener("click", () => {
      hideModal();
      clearMarks();
      enableForm(true);
      renderReview([]);
      box.style.display = "none";
      resetStepper();
    });
  }

  if (btnTry100) {
    btnTry100.addEventListener("click", () => {
      hideModal();
      clearMarks();
      enableForm(true);
      renderReview([]);
      box.style.display = "none";
      resetStepper();
    });
  }

  if (btnFinishCourse) {
    btnFinishCourse.addEventListener("click", async () => {
      if (!finalizeUrl) {
        window.location.href = coursesUrl;
        return;
      }

      btnFinishCourse.disabled = true;

      try {
        const res = await fetch(finalizeUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
          body: JSON.stringify({ finalize: true }),
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data && data.message ? data.message : "No se pudo finalizar el curso.");
        }

        const redirectUrl = data && data.redirect_url ? data.redirect_url : "";
        window.location.href = redirectUrl || coursesUrl;
      } catch (e) {
        btnFinishCourse.disabled = false;
        box.style.display = "block";
        box.classList.remove("alert-success");
        box.classList.add("alert-danger");
        box.textContent = e && e.message ? e.message : "Error al finalizar.";
      }
    });
  }

  btnSubmit.addEventListener("click", async () => {
    if (answeredCount() !== totalQ) {
      box.style.display = "block";
      box.classList.remove("alert-success");
      box.classList.add("alert-warning");
      box.textContent = "Debes responder todas las preguntas antes de enviar.";
      return;
    }

    btnSubmit.disabled = true;
    box.style.display = "none";
    clearMarks();

    try {
      const fd = new FormData(form);

      const res = await fetch(submitUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: fd,
        credentials: "same-origin",
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data && data.message ? data.message : "Error al enviar el quiz.");
      }

      if (data && Array.isArray(data.details) && data.details.length) {
        markAnswers(data.details);
      }

      disableForm();

      const score = typeof data.score === "number" ? data.score : 0;
      const total = typeof data.total_questions === "number" ? data.total_questions : 0;
      const pct = typeof data.percentage_score === "number" ? data.percentage_score : 0;

      box.style.display = "block";
      box.classList.remove("alert-warning", "alert-danger");
      box.classList.add(data.passed ? "alert-success" : "alert-danger");
      box.textContent = "Resultado: " + formatScore(score) + "/" + total + " (" + Math.round(pct) + "%)";

      openResultModal(data);
    } catch (e) {
      box.style.display = "block";
      box.classList.remove("alert-success", "alert-warning");
      box.classList.add("alert-danger");
      box.textContent = e && e.message ? e.message : "Error.";
      btnSubmit.disabled = false;
    }
  });
})();
