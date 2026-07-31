(() => {
  const stage = document.querySelector(".hero-stage");
  const canvas = document.getElementById("particle-canvas");
  if (!stage || !canvas) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  const particles = [];
  const pointer = { x: -9999, y: -9999, active: false };

  let width = 0;
  let height = 0;
  let dpr = 1;
  let raf = 0;

  const build = () => {
    particles.length = 0;
    const cols = width < 700 ? 18 : width < 1100 ? 26 : 34;
    const rows = height < 500 ? 36 : 52;
    const colGap = width / (cols + 1);
    const rowGap = height / (rows + 1);

    for (let c = 0; c < cols; c += 1) {
      const baseX = colGap * (c + 1);
      for (let r = 0; r < rows; r += 1) {
        const wave = Math.sin(c * 0.55 + r * 0.18) * 10;
        const x = baseX + wave + (Math.random() - 0.5) * 3;
        const y = rowGap * (r + 1) + (Math.random() - 0.5) * 4;
        particles.push({
          ox: x,
          oy: y,
          x,
          y,
          vx: 0,
          vy: 0,
          r: 1.1 + Math.random() * 0.9,
        });
      }
    }
  };

  const resize = () => {
    const rect = stage.getBoundingClientRect();
    width = Math.max(1, Math.floor(rect.width));
    height = Math.max(1, Math.floor(rect.height));
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
    if (reduceMotion) draw();
  };

  const draw = () => {
    ctx.clearRect(0, 0, width, height);
    // Soft coral like the reference, tuned for a dark page.
    ctx.fillStyle = "rgba(232, 140, 122, 0.55)";
    for (const p of particles) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const step = () => {
    raf = window.requestAnimationFrame(step);

    const radius = Math.min(width, height) * 0.16;
    const radius2 = radius * radius;
    const strength = 28;
    const ease = 0.08;
    const damp = 0.78;

    for (const p of particles) {
      let fx = 0;
      let fy = 0;

      if (pointer.active) {
        const dx = p.x - pointer.x;
        const dy = p.y - pointer.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < radius2 && d2 > 0.01) {
          const d = Math.sqrt(d2);
          const force = ((radius - d) / radius) ** 1.35;
          fx += (dx / d) * force * strength;
          fy += (dy / d) * force * strength;
        }
      }

      // Spring back to home position.
      fx += (p.ox - p.x) * ease;
      fy += (p.oy - p.y) * ease;

      p.vx = (p.vx + fx) * damp;
      p.vy = (p.vy + fy) * damp;
      p.x += p.vx;
      p.y += p.vy;
    }

    draw();
  };

  stage.addEventListener(
    "pointermove",
    (e) => {
      const rect = stage.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
      pointer.active = true;
    },
    { passive: true },
  );

  stage.addEventListener(
    "pointerleave",
    () => {
      pointer.active = false;
    },
    { passive: true },
  );

  window.addEventListener("resize", resize);
  resize();

  if (!reduceMotion) {
    raf = window.requestAnimationFrame(step);
  } else {
    draw();
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      window.cancelAnimationFrame(raf);
    } else if (!reduceMotion) {
      raf = window.requestAnimationFrame(step);
    }
  });
})();
