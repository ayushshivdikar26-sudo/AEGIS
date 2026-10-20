/**
 * AEGIS Risk Gauge & Risk Assessment Renderer (render/gauge.js)
 * Implements:
 *  - Row 1 Right Card: Centered speedometer gauge, score / 100, level chip, and disclaimer (Part C5).
 *  - Row 2 Card: "Risk assessment" heading, 2-column container card with explanation, plain summary,
 *    main risk contributors, calculation disclosure, and bottom excess score strip (Part C5).
 */

import { h } from "../dom.js";
import { arcPath, scoreToAngle, scoreToLevel } from "../lib/risk.js";

/**
 * Builds the SVG speedometer element.
 */
function createSpeedometerSVG(score) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 240 140");
  svg.setAttribute("class", "gauge-svg");

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

  // Needle
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
  const textProps = { fill: "var(--text-muted)", "font-size": "11", "font-family": "IBM Plex Mono, monospace" };
  const tick0 = document.createElementNS("http://www.w3.org/2000/svg", "text");
  tick0.setAttribute("x", "12");
  tick0.setAttribute("y", "136");
  for (const [k, v] of Object.entries(textProps)) tick0.setAttribute(k, v);
  tick0.textContent = "0";

  const tick100 = document.createElementNS("http://www.w3.org/2000/svg", "text");
  tick100.setAttribute("x", "208");
  tick100.setAttribute("y", "136");
  for (const [k, v] of Object.entries(textProps)) tick100.setAttribute(k, v);
  tick100.textContent = "100";

  svg.appendChild(needleGroup);
  svg.appendChild(tick0);
  svg.appendChild(tick100);

  return svg;
}

/**
 * Renders Row 1 Right Card: Centered Risk Gauge.
 */
export function renderGauge(assessmentData) {
  const panel = h("section", {
    id: "gauge-section",
    className: "panel gauge-card",
    "aria-labelledby": "gauge-heading",
  });

  const assess = assessmentData || {};
  const score = assess.risk_score || 0;
  const level = assess.risk_level || scoreToLevel(score);

  const svg = createSpeedometerSVG(score);

  // Number counting element
  const scoreNumSpan = h("span", { id: "gauge-score-num" }, String(score));

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!prefersReduced) {
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
  return panel;
}

/**
 * Renders Row 2: Section Heading "Risk assessment" + Container Card with 2 columns.
 */
export function renderRiskAssessment(assessmentData) {
  const container = h("div", { className: "risk-assessment-section-wrapper" });

  // 1. Plain section heading above the card
  container.appendChild(
    h("h2", { className: "dashboard-section-heading" }, "Risk assessment")
  );

  const assess = assessmentData || {};
  const level = assess.risk_level || scoreToLevel(assess.risk_score || 0);

  // 2. Container Card
  const card = h("section", {
    id: "risk-assessment-card",
    className: "panel risk-assessment-card",
  });

  // Top Grid: 2 Columns
  const grid = h("div", { className: "risk-assessment-grid" });

  // Column 1 (Left): Two stacked boxes
  const leftCol = h("div", { className: "risk-col-left" });

  let levelTitle = "Routine Exposure";
  let levelDesc = "This extension requests standard capabilities needed for basic tasks with minimal data exposure.";
  let levelColor = "var(--risk-low)";

  if (level === "mid" || level === "medium") {
    levelTitle = "Moderate Exposure";
    levelDesc = "This extension requests moderate capabilities (such as inspecting active browser tabs or specific website domains).";
    levelColor = "var(--risk-mid)";
  } else if (level === "high" || level === "critical") {
    levelTitle = "Broad / Sensitive Exposure";
    levelDesc = "This extension requests access to sensitive browser features (such as browsing history or cookies) or unrestricted access to all websites.";
    levelColor = "var(--risk-high)";
  }

  // Box 1: Understanding This Score
  const explanationBox = h(
    "div",
    { className: "risk-explanation-box" },
    h(
      "div",
      { className: "risk-card-header" },
      h("span", { className: "status-dot", style: { "background-color": levelColor } }),
      h("strong", null, `Understanding This Score: ${levelTitle}`)
    ),
    h("p", { className: "risk-card-body" }, levelDesc),
    h(
      "p",
      { className: "risk-card-disclaimer" },
      "Objective audit note: This score measures declared capability and exposure scope. It does not imply malicious intent."
    )
  );
  leftCol.appendChild(explanationBox);

  // Box 2: Plain-language summary sentence
  if (assess.plain_summary) {
    const summaryBox = h(
      "div",
      { className: "risk-summary-box" },
      h("div", { className: "risk-summary-label" }, "Summary Assessment"),
      h("p", { className: "risk-summary-text", dir: "auto" }, assess.plain_summary)
    );
    leftCol.appendChild(summaryBox);
  }
  grid.appendChild(leftCol);

  // Column 2 (Right): Main risk contributors box + Calculation disclosure button
  const rightCol = h("div", { className: "risk-col-right" });

  const contribBox = h("div", { className: "risk-contributors-box" });
  contribBox.appendChild(
    h("div", { className: "contributors-header" }, "Main risk contributors")
  );

  const top3 = (assess.breakdown || []).slice(0, 3);
  if (top3.length > 0) {
    const contribList = h("div", { className: "contributors-list" });
    for (const item of top3) {
      contribList.appendChild(
        h(
          "div",
          { className: "contributor-item" },
          h("span", { className: "mono contributor-label" }, item.label),
          h("span", { className: "mono contributor-value" }, `+${item.contribution.toFixed(1)}`)
        )
      );
    }
    contribBox.appendChild(contribList);
  } else {
    contribBox.appendChild(
      h("div", { className: "contributor-empty" }, "No individual risk contributors.")
    );
  }
  rightCol.appendChild(contribBox);

  // Calculation disclosure link/button
  if (assess.calculation && assess.calculation.length > 0) {
    const disclosureBtn = h(
      "button",
      {
        type: "button",
        className: "calc-disclosure-btn",
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
          { className: "calc-step-row" },
          h("span", { className: "mono calc-step-name" }, `${step.step}: `),
          h("span", null, `${step.formula} = `),
          h("span", { className: "mono" }, `${step.values} -> `),
          h("span", { className: "mono calc-step-res" }, step.result)
        )
      );
    }

    disclosureBtn.addEventListener("click", () => {
      const isExpanded = disclosureBtn.getAttribute("aria-expanded") === "true";
      disclosureBtn.setAttribute("aria-expanded", String(!isExpanded));
      stepsContainer.style.setProperty("display", isExpanded ? "none" : "flex");
    });

    rightCol.appendChild(disclosureBtn);
    rightCol.appendChild(stepsContainer);
  }
  grid.appendChild(rightCol);

  card.appendChild(grid);

  // Full-width Bottom Strip: Excess Score / Evidence Coverage
  if (assess.excess_score !== undefined || assess.evidence_coverage !== undefined) {
    const excessVal =
      assess.excess_score !== null && assess.excess_score !== undefined
        ? `${assess.excess_score} / 100`
        : "Not enough evidence to estimate";

    const strip = h(
      "div",
      { className: "excess-score-strip" },
      h(
        "div",
        { className: "strip-item" },
        h("span", { className: "strip-label" }, "Excess score: "),
        h("span", { className: "mono strip-value" }, excessVal)
      ),
      assess.evidence_coverage !== undefined && assess.evidence_coverage !== null
        ? h(
            "div",
            { className: "strip-item" },
            h("span", { className: "strip-label" }, "Evidence coverage: "),
            h("span", { className: "mono strip-value" }, `${Math.round(assess.evidence_coverage * 100)}%`)
          )
        : null
    );
    card.appendChild(strip);
  }

  container.appendChild(card);
  return container;
}
