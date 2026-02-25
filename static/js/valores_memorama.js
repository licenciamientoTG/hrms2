// =========================================================
// VALORES MEMORAMA (aislado)
// =========================================================

(() => {
  const root = document.querySelector(".page.valores-memorama");
  if (!root) return;

  const isMobileViewport = window.matchMedia("(max-width: 991.98px)").matches;
  if (isMobileViewport) {
    const titlesGroup = root.querySelector('[data-group="titles"]');
    const descriptionsGroup = root.querySelector('[data-group="descriptions"]');
    const titlesGrid = titlesGroup ? titlesGroup.querySelector('[data-grid="titles"]') : null;
    const descriptionsGrid = descriptionsGroup
      ? descriptionsGroup.querySelector('[data-grid="descriptions"]')
      : null;

    if (titlesGrid && descriptionsGrid) {
      Array.from(descriptionsGrid.querySelectorAll("[data-card]")).forEach((card) => {
        titlesGrid.appendChild(card);
      });
      descriptionsGroup.classList.add("d-none");
      root.classList.add("is-mobile-merged");
    }
  }

  const cardGrids = root.querySelectorAll(".card-grid");
  const MATCH_DELAY_MS = 650;


  const MATCH_COLORS = [
    "#014AA9", // azul base
    "#9DC72E", // verde-lima base
    "#009558", // verde base
    "#009CDF", // cyan base

    "#0e69e1", // azul base
    "#c7de8a", // verde-lima base
    "#37c68a", // verde base
  ];


  const shuffleCardsInGrid = (grid) => {
    const cards = Array.from(grid.querySelectorAll("[data-card]"));
    for (let i = cards.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [cards[i], cards[j]] = [cards[j], cards[i]];
    }
    cards.forEach((card) => grid.appendChild(card));
  };

  cardGrids.forEach((grid) => shuffleCardsInGrid(grid));

  const cards = root.querySelectorAll("[data-card]");
  let flippedCards = [];
  let isChecking = false;
  let matchedPairsCount = 0;

  // Total de pares (por letras únicas)
  const totalPairs = new Set(
    Array.from(cards).map((c) => (c.dataset.letter || "").trim())
  ).size;

  // Evitar disparar completado varias veces
  let gameCompleted = false;

  // =========================================================
  // CONFETTI (Canvas overlay, sin librerías)
  // - burstConfettiAt(x,y): confeti en un punto (para match)
  // - startWinConfetti(): confeti grande (al completar)
  // =========================================================

  const confetti = {
    canvas: null,
    ctx: null,
    raf: 0,
    running: false,
    particles: [],
    resizeBound: false,

    // control de modos/tiempos
    winMode: false,
    spawnUntil: 0,
    stopAt: 0,
    idleUntil: 0,
  };

  const getConfettiCanvas = () => {
    if (confetti.canvas) return confetti.canvas;
    confetti.canvas = document.getElementById("memoramaConfetti");
    if (!confetti.canvas) return null;
    confetti.ctx = confetti.canvas.getContext("2d");
    return confetti.canvas;
  };

  const resizeConfetti = () => {
    const c = getConfettiCanvas();
    if (!c) return;

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.floor(window.innerWidth * dpr);
    c.height = Math.floor(window.innerHeight * dpr);
    c.style.width = "100vw";
    c.style.height = "100vh";

    // Dibujar en unidades CSS px (coordenadas fáciles)
    confetti.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const rand = (min, max) => Math.random() * (max - min) + min;

  const ensureConfettiEngine = () => {
    const c = getConfettiCanvas();
    if (!c) return false;

    resizeConfetti();

    if (!confetti.resizeBound) {
      window.addEventListener("resize", resizeConfetti);
      confetti.resizeBound = true;
    }

    c.style.display = "block";

    if (!confetti.running) {
      confetti.running = true;
      confetti.raf = requestAnimationFrame(confettiLoop);
    }

    return true;
  };

  const spawnFromTop = (amount) => {
    const w = window.innerWidth;
    const palette = [...MATCH_COLORS, "#ffffff", "#0f172a"];

    for (let i = 0; i < amount; i += 1) {
      const size = rand(5, 10);
      confetti.particles.push({
        x: rand(0, w),
        y: rand(-24, -6),
        vx: rand(-2.2, 2.2),
        vy: rand(2.2, 6.0),
        g: rand(0.06, 0.12),
        r: rand(0, Math.PI * 2),
        vr: rand(-0.18, 0.18),
        w: size * rand(0.9, 1.7),
        h: size * rand(0.6, 1.4),
        color: palette[Math.floor(rand(0, palette.length))],
        alpha: rand(0.85, 1),
      });
    }
  };

  const burstConfettiAt = (x, y, amount, mainColor) => {
    if (!ensureConfettiEngine()) return;

    const palette = [mainColor, ...MATCH_COLORS, "#ffffff"];
    const now = performance.now();

    // Mantener el canvas vivo un rato aunque se acaben partículas
    confetti.idleUntil = Math.max(confetti.idleUntil, now + 700);

    for (let i = 0; i < amount; i += 1) {
      const size = rand(5, 10);
      const angle = rand(0, Math.PI * 2);
      const speed = rand(2.2, 6.5);

      // Explosión con bias hacia arriba
      const vx = Math.cos(angle) * speed;
      const vy = Math.sin(angle) * speed - rand(2.8, 5.2);

      confetti.particles.push({
        x,
        y,
        vx,
        vy,
        g: rand(0.08, 0.14),
        r: rand(0, Math.PI * 2),
        vr: rand(-0.22, 0.22),
        w: size * rand(0.8, 1.6),
        h: size * rand(0.6, 1.3),
        color: palette[Math.floor(rand(0, palette.length))],
        alpha: rand(0.85, 1),
      });
    }
  };

  const startWinConfetti = () => {
    if (!ensureConfettiEngine()) return;

    const now = performance.now();
    confetti.winMode = true;

    // burst fuerte + chorro corto
    spawnFromTop(160);
    confetti.spawnUntil = now + 900;
    confetti.stopAt = now + 2600;

    // mantener vivo un poco
    confetti.idleUntil = Math.max(confetti.idleUntil, now + 1200);
  };

  const stopConfetti = () => {
    confetti.running = false;
    confetti.winMode = false;

    if (confetti.raf) cancelAnimationFrame(confetti.raf);
    confetti.raf = 0;

    confetti.particles = [];
    confetti.spawnUntil = 0;
    confetti.stopAt = 0;
    confetti.idleUntil = 0;

    const c = getConfettiCanvas();
    if (c && confetti.ctx) {
      confetti.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      c.style.display = "none";
    }

    if (confetti.resizeBound) {
      window.removeEventListener("resize", resizeConfetti);
      confetti.resizeBound = false;
    }
  };

  const confettiLoop = (t) => {
    if (!confetti.running) return;

    const ctx = confetti.ctx;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    // Modo win: seguir soltando desde arriba
    if (confetti.winMode && t < confetti.spawnUntil) {
      spawnFromTop(18);
    }

    const w = window.innerWidth;
    const h = window.innerHeight;

    for (let i = confetti.particles.length - 1; i >= 0; i -= 1) {
      const p = confetti.particles[i];

      p.vy += p.g;
      p.x += p.vx;
      p.y += p.vy;
      p.r += p.vr;

      if (p.y > h + 60 || p.x < -80 || p.x > w + 80) {
        confetti.particles.splice(i, 1);
        continue;
      }

      ctx.save();
      ctx.globalAlpha = p.alpha;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.r);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }

    const deadline = Math.max(confetti.stopAt, confetti.idleUntil);
    const shouldStop = confetti.particles.length === 0 && t > deadline;

    if (shouldStop) {
      stopConfetti();
      return;
    }

    confetti.raf = requestAnimationFrame(confettiLoop);
  };

  // =========================================================
  // MODAL COMPLETADO (Bootstrap si existe, fallback si no)
  // =========================================================

  const showCompleteModal = () => {
    const modalEl = document.getElementById("memoramaCompleteModal");
    if (!modalEl) return;

    // Actualiza label 7/7
    const pairsLabel = document.getElementById("memoramaPairsLabel");
    if (pairsLabel) pairsLabel.textContent = `${matchedPairsCount}/${totalPairs}`;

    // Bootstrap 5
    if (window.bootstrap && window.bootstrap.Modal) {
      const instance = window.bootstrap.Modal.getOrCreateInstance(modalEl, {
        backdrop: "static",
        keyboard: true,
      });
      instance.show();
      return;
    }

    // Bootstrap 4 con jQuery
    if (window.jQuery && typeof window.jQuery(modalEl).modal === "function") {
      window.jQuery(modalEl).modal({ backdrop: "static", keyboard: true, show: true });
      return;
    }

    // Fallback manual (sin JS de Bootstrap)
    modalEl.classList.add("show");
    modalEl.style.display = "block";
    modalEl.removeAttribute("aria-hidden");
    modalEl.setAttribute("aria-modal", "true");

    document.body.classList.add("modal-open");

    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop fade show";
    backdrop.setAttribute("data-memorama-backdrop", "1");
    document.body.appendChild(backdrop);

    document.body.style.overflow = "hidden";
  };

  const hideCompleteModal = () => {
    const modalEl = document.getElementById("memoramaCompleteModal");
    if (!modalEl) return;

    // Bootstrap 5
    if (window.bootstrap && window.bootstrap.Modal) {
      const instance = window.bootstrap.Modal.getInstance(modalEl);
      if (instance) instance.hide();
      return;
    }

    // Bootstrap 4
    if (window.jQuery && typeof window.jQuery(modalEl).modal === "function") {
      window.jQuery(modalEl).modal("hide");
      return;
    }

    // Fallback manual
    modalEl.classList.remove("show");
    modalEl.style.display = "none";
    modalEl.setAttribute("aria-hidden", "true");
    modalEl.removeAttribute("aria-modal");

    document.body.classList.remove("modal-open");

    const backdrop = document.querySelector('[data-memorama-backdrop="1"]');
    if (backdrop) backdrop.remove();

    document.body.style.overflow = "";
  };

  const onGameComplete = () => {
    if (gameCompleted) return;
    gameCompleted = true;

    // Bloquear interacciones
    cards.forEach((c) => {
      c.style.pointerEvents = "none";
      c.setAttribute("tabindex", "-1");
    });

    // Confetti + modal
    startWinConfetti();
    showCompleteModal();
  };

  // Botones del modal
  const wireCompleteModalButtons = () => {
    const btnClose = document.getElementById("btnMemoramaClose");
    const btnReplay = document.getElementById("btnMemoramaReplay");
    const modalEl = document.getElementById("memoramaCompleteModal");

    if (btnClose) {
      btnClose.addEventListener("click", () => {
        stopConfetti();
        hideCompleteModal();
      });
    }

    if (btnReplay) {
      btnReplay.addEventListener("click", () => {
        window.location.reload();
      });
    }

    // Si Bootstrap dispara eventos, apagamos confetti al cerrar
    if (modalEl) {
      modalEl.addEventListener("hidden.bs.modal", () => stopConfetti());
      modalEl.addEventListener("hide.bs.modal", () => stopConfetti());
    }

    // ESC fallback
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        stopConfetti();
        hideCompleteModal();
      }
    });
  };

  wireCompleteModalButtons();

  // =========================================================
  // AUDIO (más robusto Safari/iOS)
  // =========================================================
  let audioContext = null;
  let audioUnlocked = false;

  const getAudioContext = () => {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
  };

  const unlockAudioHard = async () => {
    try {
      const ctx = getAudioContext();

      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      const o = ctx.createOscillator();
      const g = ctx.createGain();

      g.gain.setValueAtTime(0.0001, ctx.currentTime);
      o.frequency.setValueAtTime(440, ctx.currentTime);
      o.connect(g);
      g.connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + 0.01);

      audioUnlocked = true;
    } catch (e) {}
  };

  window.addEventListener("pointerdown", unlockAudioHard, { once: true, passive: true });
  window.addEventListener("touchstart", unlockAudioHard, { once: true, passive: true });
  window.addEventListener("keydown", unlockAudioHard, { once: true });

  const playMatchSound = async () => {
    try {
      const ctx = getAudioContext();

      if (ctx.state === "suspended") {
        await ctx.resume();
      }
      if (ctx.state !== "running") return;

      if (!audioUnlocked) {
        await unlockAudioHard();
        if (ctx.state !== "running") return;
      }

      const now = ctx.currentTime;

      const gainNode = ctx.createGain();
      gainNode.gain.setValueAtTime(0.0, now);
      gainNode.gain.linearRampToValueAtTime(0.25, now + 0.015);
      gainNode.gain.linearRampToValueAtTime(0.0, now + 0.35);
      gainNode.connect(ctx.destination);

      const oscOne = ctx.createOscillator();
      oscOne.type = "sine";
      oscOne.frequency.setValueAtTime(523.25, now);
      oscOne.connect(gainNode);
      oscOne.start(now);
      oscOne.stop(now + 0.18);

      const oscTwo = ctx.createOscillator();
      oscTwo.type = "sine";
      oscTwo.frequency.setValueAtTime(659.25, now + 0.09);
      oscTwo.connect(gainNode);
      oscTwo.start(now + 0.09);
      oscTwo.stop(now + 0.30);
    } catch (e) {}
  };

  const flipCard = (card) => {
    card.classList.add("is-flipped");
    card.setAttribute("aria-pressed", "true");
  };

  const unflipCard = (card) => {
    card.classList.remove("is-flipped");
    card.setAttribute("aria-pressed", "false");
  };

  const markMatched = (firstCard, secondCard, color) => {
    [firstCard, secondCard].forEach((card) => {
      card.style.setProperty("--match-color", color);
      card.classList.add("is-matched");
    });
  };

  const handleCardSelection = (card) => {
    if (isChecking) return;
    if (card.classList.contains("is-matched")) return;
    if (card.classList.contains("is-flipped")) return;

    flipCard(card);
    flippedCards.push(card);

    if (flippedCards.length !== 2) return;

    isChecking = true;
    const [firstCard, secondCard] = flippedCards;

    const isMatch =
      (firstCard.dataset.letter || "") === (secondCard.dataset.letter || "");

    if (isMatch) {
      const matchColor = MATCH_COLORS[matchedPairsCount % MATCH_COLORS.length];
      matchedPairsCount += 1;

      setTimeout(() => {
        markMatched(firstCard, secondCard, matchColor);
        playMatchSound();

        // Confeti al encontrar par (burst en el centro de ambas cartas)
        const r1 = firstCard.getBoundingClientRect();
        const r2 = secondCard.getBoundingClientRect();
        const cx = ((r1.left + r1.width / 2) + (r2.left + r2.width / 2)) / 2;
        const cy = ((r1.top + r1.height / 2) + (r2.top + r2.height / 2)) / 2;
        burstConfettiAt(cx, cy, 70, matchColor);

        flippedCards = [];
        isChecking = false;

        if (matchedPairsCount >= totalPairs) {
          onGameComplete();
        }
      }, MATCH_DELAY_MS);

      return;
    }

    setTimeout(() => {
      unflipCard(firstCard);
      unflipCard(secondCard);
      flippedCards = [];
      isChecking = false;
    }, 900);
  };

  // Listeners por carta
  cards.forEach((card) => {
    card.addEventListener(
      "pointerdown",
      () => {
        unlockAudioHard();
      },
      { passive: true }
    );

    card.addEventListener("click", () => {
      handleCardSelection(card);
    });

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleCardSelection(card);
      }
    });
  });

  // Subrayar la letra dentro del título (cara trasera con h3)
  cards.forEach((card) => {
    const letter = (card.dataset.letter || "").toUpperCase();
    if (!letter) return;

    const titles = card.querySelectorAll(".card-back h3");

    titles.forEach((h3) => {
      const originalText = h3.textContent || "";
      const upperText = originalText.toUpperCase();
      const index = upperText.indexOf(letter);

      if (index === -1) return;

      const before = originalText.slice(0, index);
      const char = originalText.slice(index, index + 1);
      const after = originalText.slice(index + 1);

      h3.innerHTML = `${before}<span class="value-letter">${char}</span>${after}`;
    });
  });
})();
