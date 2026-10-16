/**
 * AEGIS Indigo Threads Canvas Generator (threads.js)
 * Implements mathematical strand curves, dual-pass rendering, and reduced-motion compliance (Part 1 s6).
 */

export function initThreads(canvasId = "threads") {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.getContext) {
    return;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  // Check reduced motion preference
  const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let isReducedMotion = reducedMotionQuery.matches;
  reducedMotionQuery.addEventListener("change", (e) => {
    isReducedMotion = e.matches;
    if (isReducedMotion) {
      drawFrame(0);
    }
  });

  // Read CSS thread colors
  const rootStyles = getComputedStyle(document.documentElement);
  const colors = {
    t1: rootStyles.getPropertyValue("--thread-1").trim() || "#2B2A8F",
    t2: rootStyles.getPropertyValue("--thread-2").trim() || "#4747E0",
    t3: rootStyles.getPropertyValue("--thread-3").trim() || "#6B6BF5",
    t4: rootStyles.getPropertyValue("--thread-4").trim() || "#9A9AFF",
  };

  let width = 0;
  let height = 0;
  let dpr = 1;
  let strandCount = 18;
  let strands = [];

  function getColorForSpread(absSpread) {
    if (absSpread < 0.25) return colors.t4;
    if (absSpread < 0.50) return colors.t3;
    if (absSpread < 0.75) return colors.t2;
    return colors.t1;
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    strandCount = width < 600 ? 8 : 18;
    buildStrands();

    if (isReducedMotion) {
      drawFrame(0);
    }
  }

  function buildStrands() {
    strands = [];
    const step = strandCount > 1 ? 2 / (strandCount - 1) : 0;
    for (let i = 0; i < strandCount; i++) {
      const s_i = -1 + i * step; // Spread in [-1, 1]
      strands.push({
        s_i,
        f_i: 0.8 + ((i * 7) % 5) * 0.1, // Frequency variations
        T_i: 22 + (i % 8), // Period 22s - 29s
        phi_i: (i * Math.PI) / 4, // Phase offset
        color: getColorForSpread(Math.abs(s_i)),
        baseAlpha: 0.06 + 0.3 * Math.pow(1 - Math.abs(s_i), 2),
      });
    }
  }

  let resizeTimeout;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(resize, 150);
  });

  resize();

  let lastTime = performance.now();
  let accumulatedTime = 0;
  const fpsInterval = 1000 / 30; // 30 FPS cap
  let animId = null;

  function drawFrame(tSeconds) {
    ctx.clearRect(0, 0, width, height);

    const T_main = 25; // 25s main period
    const samples = 60;

    for (const strand of strands) {
      const points = [];

      for (let s = 0; s <= samples; s++) {
        const u = s / samples;
        // Bundle centerline c(u): diagonal + gentle S-curve
        const diagY = 0.85 - 0.70 * u;
        const sCurve = 0.06 * Math.sin(2 * Math.PI * (0.8 * u + tSeconds / T_main));
        const c_u = diagY + sCurve;

        // Bundle width w(u): narrow at 0.45, fans out to edges
        const w_u = 0.03 + 0.5 * Math.pow(u - 0.45, 2);

        // Strand y coordinate
        const wave = 0.015 * Math.sin(2 * Math.PI * (strand.f_i * u + tSeconds / strand.T_i + strand.phi_i));
        const y_norm = c_u + strand.s_i * w_u + wave;

        points.push({
          x: u * width,
          y: y_norm * height,
        });
      }

      if (points.length < 2) continue;

      // Draw Path Helper
      function tracePath() {
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let j = 1; j < points.length - 1; j++) {
          const xc = (points[j].x + points[j + 1].x) / 2;
          const yc = (points[j].y + points[j + 1].y) / 2;
          ctx.quadraticCurveTo(points[j].x, points[j].y, xc, yc);
        }
        ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
      }

      // Pass 1: Soft wide glow
      ctx.save();
      ctx.strokeStyle = strand.color;
      ctx.lineWidth = 6;
      ctx.globalAlpha = Math.min(0.35, strand.baseAlpha * 0.25);
      tracePath();
      ctx.stroke();
      ctx.restore();

      // Pass 2: Bright thin core
      ctx.save();
      ctx.strokeStyle = strand.color;
      ctx.lineWidth = 1.2;
      ctx.globalAlpha = Math.min(0.8, strand.baseAlpha * 1.5);
      tracePath();
      ctx.stroke();
      ctx.restore();
    }
  }

  function loop(currentTime) {
    if (isReducedMotion || document.hidden) {
      animId = requestAnimationFrame(loop);
      return;
    }

    const elapsed = currentTime - lastTime;
    if (elapsed > fpsInterval) {
      lastTime = currentTime - (elapsed % fpsInterval);
      accumulatedTime += elapsed / 1000;
      drawFrame(accumulatedTime);
    }

    animId = requestAnimationFrame(loop);
  }

  // Pause loop when document is hidden
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !isReducedMotion) {
      lastTime = performance.now();
    }
  });

  if (isReducedMotion) {
    drawFrame(0);
  } else {
    animId = requestAnimationFrame(loop);
  }
}
