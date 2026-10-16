/**
 * AEGIS Risk Gauge Renderer (render/gauge.js)
 * Implements SVG speedometer with flat arcs, animated needle, number counting,
 * top-3 contributors, and explainability calculations disclosure (Part 1 s7.2, FR-F3, FR-E2).
 */

import { h } from "../dom.js";
import { arcPath, scoreToAngle, scoreToLevel } from "../lib/risk.js";

export function renderGauge(assessmentData) {
  const panel = h("section", {
    id: "gauge-section",
    className: "panel",
    "aria-labelledby": "gauge-heading",
  });

  const assess = assessmentData || {};
  const score = assess.risk_score || 0;
  const level = assess.risk_level || scoreToLevel(score);
  const thresholds = assess.thresholds || { low_max: 34, mid_max: 69 };

  // Section Heading
  panel.appendChild(
    h("div", { className: "section-label", id: "gauge-heading" }, "Risk Assessment")
  );

  // SVG Gauge Semicircle with smooth gradient
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 240 140");
  svg.setAttribute("class", "gauge-svg");

  // Linear Gradient definition across semicircle
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const grad = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
  grad.setAttribute("id", "gauge-gradient");
  grad.setAttribute("x1", "0%");
  grad.setAttribute("y1", "0%");
  grad.setAttribute("x2", "100%");
  grad.setAttribute("y2", "0%");

  const stops = [
    { offset: "0%", color: "#22C55E" },
    { offset: "35%", color: "#84CC16" },
    { offset: "65%", color: "#F59E0B" },
    { offset: "100%", color: "#EF4444" },
  ];
  for (const s of stops) {
    const stopEl = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    stopEl.setAttribute("offset", s.offset);
    stopEl.setAttribute("stop-color", s.color);
    grad.appendChild(stopEl);
  }
  defs.appendChild(grad);
  svg.appendChild(defs);

  // Background track behind gauge
  const trackPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  trackPath.setAttribute("d", arcPath(120, 120, 100, 0, 100));
  trackPath.setAttribute("class", "gauge-arc-track");
  trackPath.setAttribute("stroke", "var(--surface-2)");
  trackPath.setAttribute("stroke-width", "14");
  trackPath.setAttribute("stroke-linecap", "round");
  trackPath.setAttribute("fill", "none");
  svg.appendChild(trackPath);

  // Continuous smooth gradient arc
  const arcGrad = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arcGrad.setAttribute("d", arcPath(120, 120, 100, 0, 100));
  arcGrad.setAttribute("class", "gauge-arc-segment");
  arcGrad.setAttribute("stroke", "url(#gauge-gradient)");
  arcGrad.setAttribute("stroke-width", "14");
  arcGrad.setAttribute("stroke-linecap", "round");
  arcGrad.setAttribute("fill", "none");
  svg.appendChild(arcGrad);

  // Needle: line from center (120, 120) pointing up
  const needleGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  needleGroup.setAttribute("class", "gauge-needle");
  needleGroup.style.setProperty("--needle", `${scoreToAngle(score)}deg`);

  const needleLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
  needleLine.setAttribute("x1", "120");
  needleLine.setAttribute("y1", "120");
  needleLine.setAttribute("x2", "120");
  needleLine.setAttribute("y2", "30");
  needleLine.setAttribute("stroke", "var(--text)");
  needleLine.setAttribute("stroke-width", "3");
  needleLine.setAttribute("stroke-linecap", "round");

  const centerCap = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  centerCap.setAttribute("cx", "120");
  centerCap.setAttribute("cy", "120");
  centerCap.setAttribute("r", "7");
  centerCap.setAttribute("fill", "var(--text)");

  needleGroup.appendChild(needleLine);
  needleGroup.appendChild(centerCap);

  // Tick labels
  const textProps = { fill: "var(--text-muted)", "font-size": "10", "font-family": "IBM Plex Mono" };
  const tick0 = document.createElementNS("http://www.w3.org/2000/svg", "text");
  tick0.setAttribute("x", "12");
  tick0.setAttribute("y", "136");
  for (const [k, v] of Object.entries(textProps)) tick0.setAttribute(k, v);
  tick0.textContent = "0";

  const tick100 = document.createElementNS("http://www.w3.org/2000/svg", "text");
  tick100.setAttribute("x", "210");
  tick100.setAttribute("y", "136");
  for (const [k, v] of Object.entries(textProps)) tick100.setAttribute(k, v);
  tick100.textContent = "100";

  svg.appendChild(needleGroup);
  svg.appendChild(tick0);
  svg.appendChild(tick100);

  // Number counting element
  const scoreNumSpan = h("span", { id: "gauge-score-num" }, String(score));

  // Reduced motion check
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!prefersReduced) {
    let current = 0;
    const duration = 1000;
    const start = performance.now();
    function animateScore(now) {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / duration);
      const val = Math.round(progress * score);
      scoreNumSpan.textContent = String(val);
      if (progress < 1) {
        requestAnimationFrame(animateScore);
      } else {
        scoreNumSpan.textContent = String(score);
      }
    }
    requestAnimationFrame(animateScore);
  }

  const gaugeWrapper = h(
    "div",
    {
      className: "gauge-container",
      role: "img",
      "aria-label": `Permission risk ${score} of 100, ${level}`,
    },
    svg,
    h("div", { className: "gauge-score-value" }, "Risk score: ", scoreNumSpan, " / 100"),
    h("div", { className: `chip chip-${level}` }, level.toUpperCase()),
    h(
      "div",
      { className: "gauge-subtext" },
      "Permission risk. This does not show that the extension is malicious."
    )
  );

  panel.appendChild(gaugeWrapper);

  // Plain-Language Summary (FR-E9)
  if (assess.plain_summary) {
    panel.appendChild(
      h(
        "div",
        {
          style: {
            "padding": "var(--s-3)",
            "background-color": "var(--surface-2)",
            "border-radius": "var(--radius)",
            "font-size": "var(--text-sm)",
            "color": "var(--text)",
          },
        },
        assess.plain_summary
      )
    );
  }

  // Excess Score & Evidence Coverage (FR-E1, PRD s4.5)
  if (assess.excess_score !== undefined || assess.evidence_coverage !== undefined) {
    const excessBox = h("div", {
      className: "excess-score-box",
      style: {
        "display": "flex",
        "justify-content": "space-between",
        "align-items": "center",
        "padding": "var(--s-2) var(--s-3)",
        "background-color": "var(--surface-2)",
        "border-radius": "var(--radius)",
        "font-size": "var(--text-xs)",
        "color": "var(--text-muted)",
        "margin-top": "var(--s-2)",
      },
    });

    const excessVal =
      assess.excess_score !== null && assess.excess_score !== undefined
        ? `${assess.excess_score} / 100`
        : "Not enough evidence to estimate";

    excessBox.appendChild(
      h(
        "div",
        null,
        h("span", { style: { "font-weight": "600", "color": "var(--text)" } }, "Excess score: "),
        h("span", { className: "mono" }, excessVal)
      )
    );

    if (assess.evidence_coverage !== undefined && assess.evidence_coverage !== null) {
      excessBox.appendChild(
        h(
          "div",
          null,
          h("span", { style: { "font-weight": "600", "color": "var(--text)" } }, "Evidence coverage: "),
          h("span", { className: "mono" }, `${Math.round(assess.evidence_coverage * 100)}%`)
        )
      );
    }

    panel.appendChild(excessBox);
  }

  // Top 3 Breakdown Contributors
  if (assess.breakdown && assess.breakdown.length > 0) {
    const top3 = assess.breakdown.slice(0, 3);
    const contribList = h("div", { className: "contributors-list" });
    contribList.appendChild(
      h("div", { className: "section-label" }, "Main Risk Contributors")
    );

    for (const item of top3) {
      contribList.appendChild(
        h(
          "div",
          { className: "contributor-item" },
          h("span", { className: "mono" }, item.label),
          h("span", { className: "mono" }, `+${item.contribution.toFixed(1)}`)
        )
      );
    }

    panel.appendChild(contribList);
  }

  // "How this score is calculated" Disclosure (FR-E2)
  if (assess.calculation && assess.calculation.length > 0) {
    const disclosureBtn = h(
      "button",
      {
        type: "button",
        className: "disclosure-btn",
        "aria-expanded": "false",
      },
      "How this score is calculated"
    );

    const stepsContainer = h("div", {
      className: "calculation-steps",
      style: { display: "none" },
    });

    for (const step of assess.calculation) {
      stepsContainer.appendChild(
        h(
          "div",
          null,
          h("span", { className: "mono", style: { "font-weight": "600", "color": "var(--text)" } }, `${step.step}: `),
          h("span", null, `${step.formula} = `),
          h("span", { className: "mono" }, `${step.values} -> `),
          h("span", { className: "mono", style: { "color": "var(--accent-text)" } }, step.result)
        )
      );
    }

    disclosureBtn.addEventListener("click", () => {
      const isExpanded = disclosureBtn.getAttribute("aria-expanded") === "true";
      disclosureBtn.setAttribute("aria-expanded", String(!isExpanded));
      stepsContainer.style.setProperty("display", isExpanded ? "none" : "flex");
    });

    panel.appendChild(disclosureBtn);
    panel.appendChild(stepsContainer);
  }

  return panel;
}
