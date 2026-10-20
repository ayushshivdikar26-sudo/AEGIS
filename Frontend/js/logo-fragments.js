/**
 * AEGIS Hero Logo Fragment Shader/Canvas (Frontend/js/logo-fragments.js)
 * Assembles on load (fly-in) and disintegrates on scroll (scrubbed, reversible).
 * Pre-renders jittered triangular shards to offscreen sprites.
 */

function mulberry32(a) {
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const easeOutCubic = t => 1 - Math.pow(1 - t, 3);
const easeInQuad = t => t * t;

export function mountHeroLogo({ canvas, staticImg, imageSrc = 'assets/aegis-lockup.png' }) {
  if (!canvas) return { destroy: () => {} };

  const prefersReduced = () =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  if (prefersReduced()) {
    if (staticImg) staticImg.style.display = 'block';
    canvas.style.display = 'none';
    return { destroy: () => {} };
  }

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    if (staticImg) staticImg.style.display = 'block';
    canvas.style.display = 'none';
    return { destroy: () => {} };
  }

  let rafId = null;
  let destroyed = false;
  let shards = [];
  let isLoaded = false;
  let introStartTime = null;
  let scrollProgress = 0;
  let lerpedScroll = 0;
  let isDirty = true;

  const INTRO_DELAY = 1.2; // starts 1.2s after thread intro begins
  const INTRO_DURATION = 1.4; // 1.4s convergence

  const img = new Image();
  img.src = imageSrc;

  // Track viewport sizing
  let displayW = 340;
  let displayH = 361;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);

  function resizeCanvas() {
    const isMobile = window.innerWidth < 600;
    displayW = isMobile ? Math.min(260, window.innerWidth - 48) : 340;
    displayH = Math.round(displayW * (img.naturalHeight ? img.naturalHeight / img.naturalWidth : 1.0625));
    dpr = Math.min(window.devicePixelRatio || 1, 2);

    canvas.width = Math.round(displayW * dpr);
    canvas.height = Math.round(displayH * dpr);
    canvas.style.width = `${displayW}px`;
    canvas.style.height = `${displayH}px`;
    isDirty = true;
  }

  function generateShards() {
    if (!img.naturalWidth || !img.naturalHeight) return;

    const isMobile = window.innerWidth < 600;
    const cols = isMobile ? 12 : 20;
    const rows = isMobile ? 12 : 20;
    const rand = mulberry32(0xa3915f);

    // Source image dimensions
    const sw = img.naturalWidth;
    const sh = img.naturalHeight;
    const cellW = sw / cols;
    const cellH = sh / rows;

    // Build grid of jittered vertices
    const grid = [];
    for (let r = 0; r <= rows; r++) {
      grid[r] = [];
      for (let c = 0; c <= cols; c++) {
        let x = c * cellW;
        let y = r * cellH;
        // Jitter interior points
        if (c > 0 && c < cols && r > 0 && r < rows) {
          x += (rand() - 0.5) * cellW * 0.7;
          y += (rand() - 0.5) * cellH * 0.7;
        }
        grid[r][c] = { x, y };
      }
    }

    // Helper offscreen canvas: grab full pixel data ONCE to avoid GPU readback stalls
    const probeCanvas = document.createElement('canvas');
    probeCanvas.width = sw;
    probeCanvas.height = sh;
    const probeCtx = probeCanvas.getContext('2d', { willReadFrequently: true });
    probeCtx.drawImage(img, 0, 0);
    const fullImgData = probeCtx.getImageData(0, 0, sw, sh).data;

    const centerX = sw / 2;
    const centerY = sh / 2;
    const maxRadius = Math.hypot(centerX, centerY);

    const shardList = [];

    function getPixelAlpha(x, y) {
      const cx = Math.max(0, Math.min(sw - 1, Math.round(x)));
      const cy = Math.max(0, Math.min(sh - 1, Math.round(y)));
      return fullImgData[(cy * sw + cx) * 4 + 3];
    }

    function processTriangle(p1, p2, p3) {
      const minX = Math.floor(Math.min(p1.x, p2.x, p3.x));
      const maxX = Math.ceil(Math.max(p1.x, p2.x, p3.x));
      const minY = Math.floor(Math.min(p1.y, p2.y, p3.y));
      const maxY = Math.ceil(Math.max(p1.y, p2.y, p3.y));
      const tw = maxX - minX;
      const th = maxY - minY;

      if (tw <= 2 || th <= 2) return;

      // Check if triangle has non-transparent pixels (zero GPU stall)
      const testX = (p1.x + p2.x + p3.x) / 3;
      const testY = (p1.y + p2.y + p3.y) / 3;
      const centerAlpha = getPixelAlpha(testX, testY);

      // Skip fully transparent shards
      if (centerAlpha < 10) {
        if (getPixelAlpha(p1.x, p1.y) < 10 && getPixelAlpha(p2.x, p2.y) < 10 && getPixelAlpha(p3.x, p3.y) < 10) {
          return;
        }
      }

      // Pre-render sprite into small offscreen canvas
      const shardCanvas = document.createElement('canvas');
      shardCanvas.width = tw;
      shardCanvas.height = th;
      const sCtx = shardCanvas.getContext('2d');

      sCtx.save();
      sCtx.beginPath();
      sCtx.moveTo(p1.x - minX, p1.y - minY);
      sCtx.lineTo(p2.x - minX, p2.y - minY);
      sCtx.lineTo(p3.x - minX, p3.y - minY);
      sCtx.closePath();
      sCtx.clip();

      sCtx.drawImage(img, -minX, -minY);
      sCtx.restore();

      const cx = (p1.x + p2.x + p3.x) / 3;
      const cy = (p1.y + p2.y + p3.y) / 3;
      const dx = cx - centerX;
      const dy = cy - centerY;
      const dist = Math.hypot(dx, dy);
      const normDist = dist / maxRadius;

      // Outward angle with upward drift
      const baseAngle = Math.atan2(dy, dx);
      const outwardAngle = baseAngle + (rand() - 0.5) * 0.4;
      const speed = 1.0 + rand() * 1.5;

      const vx = Math.cos(outwardAngle) * speed * 220;
      const vy = (Math.sin(outwardAngle) * speed - 0.45) * 220; // Upward drift
      const rot = (rand() - 0.5) * 3.5; // Rotation in radians

      // Intro scatter offset (fly in from outside)
      const scatterDist = 300 + rand() * 400;
      const scatterAngle = baseAngle + (rand() - 0.5) * 1.2;
      const initX = Math.cos(scatterAngle) * scatterDist;
      const initY = (Math.sin(scatterAngle) - 0.3) * scatterDist;
      const initRot = (rand() - 0.5) * 4.0;
      const introDelay = normDist * 0.4 + rand() * 0.2; // Stagger by distance from center

      shardList.push({
        canvas: shardCanvas,
        minX,
        minY,
        tw,
        th,
        origX: minX,
        origY: minY,
        vx,
        vy,
        rot,
        initX,
        initY,
        initRot,
        introDelay,
      });
    }

    // Tessellate grid into 2 triangles per cell
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const p00 = grid[r][c];
        const p10 = grid[r][c + 1];
        const p01 = grid[r + 1][c];
        const p11 = grid[r + 1][c + 1];

        processTriangle(p00, p10, p11);
        processTriangle(p00, p11, p01);
      }
    }

    shards = shardList;
    isLoaded = true;
    isDirty = true;
  }

  img.onload = () => {
    resizeCanvas();
    generateShards();
    if (staticImg) staticImg.style.display = 'none';
  };

  img.onerror = () => {
    if (staticImg) staticImg.style.display = 'block';
    canvas.style.display = 'none';
  };

  const onScroll = () => {
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const threshold = 0.9 * (window.innerHeight || 800);
    scrollProgress = Math.max(0, Math.min(1, scrollY / threshold));
    isDirty = true;
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', () => {
    resizeCanvas();
    isDirty = true;
  });

  const startTime = performance.now();

  function loop(now) {
    if (destroyed) return;
    rafId = requestAnimationFrame(loop);

    const elapsed = (now - startTime) / 1000;

    // Intro progress
    let introFinished = false;
    let introT = 0;
    if (elapsed < INTRO_DELAY) {
      introT = 0;
    } else if (elapsed < INTRO_DELAY + INTRO_DURATION) {
      introT = (elapsed - INTRO_DELAY) / INTRO_DURATION;
      isDirty = true;
    } else {
      introT = 1;
      introFinished = true;
    }

    // Scroll lerp
    const diff = scrollProgress - lerpedScroll;
    if (Math.abs(diff) > 0.001) {
      lerpedScroll += diff * 0.18;
      isDirty = true;
    } else if (lerpedScroll !== scrollProgress) {
      lerpedScroll = scrollProgress;
      isDirty = true;
    }

    // Breathing glow when idle
    const breathing = introFinished && lerpedScroll < 0.05;
    if (breathing) {
      isDirty = true;
    }

    if (!isDirty || !isLoaded) return;
    isDirty = false;

    // Render frame
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Scale from source image space (sw, sh) to canvas pixels
    const scale = (displayW * dpr) / img.naturalWidth;
    ctx.scale(scale, scale);

    // Breathing glow amplitude (gentle 4-second sine cycle)
    const glowCycle = Math.sin(now / 650);
    const glowBlur = (8 + glowCycle * 4) * dpr;
    ctx.shadowColor = 'rgba(16, 176, 240, 0.45)';
    ctx.shadowBlur = glowBlur;

    const p = lerpedScroll;

    for (let i = 0; i < shards.length; i++) {
      const s = shards[i];

      let x = s.origX;
      let y = s.origY;
      let angle = 0;
      let alpha = 1.0;
      let shardScale = 1.0;

      // 1. Intro convergence
      if (!introFinished) {
        const localT = Math.max(0, Math.min(1, (introT - s.introDelay) / (1 - s.introDelay)));
        const easeT = easeOutCubic(localT);

        x += s.initX * (1 - easeT);
        y += s.initY * (1 - easeT);
        angle += s.initRot * (1 - easeT);
        alpha *= easeT;
      }

      // 2. Scroll disintegration (scrubbed)
      if (p > 0.001) {
        const pEased = Math.pow(p, 1.2);
        x += s.vx * pEased;
        y += s.vy * pEased;
        angle += s.rot * pEased;
        shardScale = Math.max(0.01, 1.0 - 0.35 * p);
        alpha *= Math.max(0, 1.0 - Math.pow(p, 1.4));
      }

      if (alpha <= 0.01 || shardScale <= 0.01) continue;

      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));

      // Translate to shard center, apply transform, and draw sprite
      const cx = x + s.tw / 2;
      const cy = y + s.th / 2;
      ctx.translate(cx, cy);
      if (angle !== 0) ctx.rotate(angle);
      if (shardScale !== 1.0) ctx.scale(shardScale, shardScale);

      ctx.drawImage(s.canvas, -s.tw / 2, -s.th / 2);
      ctx.restore();
    }

    ctx.restore();
  }

  rafId = requestAnimationFrame(loop);

  return {
    destroy() {
      destroyed = true;
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener('scroll', onScroll);
    },
  };
}
