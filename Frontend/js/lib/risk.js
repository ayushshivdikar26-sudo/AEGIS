/**
 * AEGIS Risk Math & Gauge Utilities (Frontend/js/lib/risk.js)
 * Implements threshold mapping, semicircle coordinates, and SVG arc generation.
 */

export function scoreToLevel(score, thresholds = { low_max: 34, mid_max: 69 }) {
  const s = Number(score) || 0;
  if (s <= thresholds.low_max) {
    return "low";
  }
  if (s <= thresholds.mid_max) {
    return "medium";
  }
  return "high";
}

export function scoreToAngle(score) {
  const s = Number(score) || 0;
  const clamped = Math.max(0, Math.min(100, s));
  return -90 + (clamped / 100) * 180;
}

export function pointOnArc(cx, cy, r, score) {
  const s = Number(score) || 0;
  const clamped = Math.max(0, Math.min(100, s));
  const rad = (clamped / 100) * Math.PI;
  const x = Math.round(cx - r * Math.cos(rad));
  const y = Math.round(cy - r * Math.sin(rad));
  return { x, y };
}

export function arcPath(cx, cy, r, startScore, endScore) {
  const start = pointOnArc(cx, cy, r, startScore);
  const end = pointOnArc(cx, cy, r, endScore);
  const largeArcFlag = Math.abs(endScore - startScore) > 100 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`;
}

export function scoreColor(score, thresholds = { low_max: 34, mid_max: 69 }) {
  const level = scoreToLevel(score, thresholds);
  if (level === "low") {
    return "var(--risk-low)";
  }
  if (level === "medium") {
    return "var(--risk-mid)";
  }
  return "var(--risk-high)";
}
