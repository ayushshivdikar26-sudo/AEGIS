/**
 * AEGIS Permission Creep Renderer (render/creep.js)
 * Displays creep classification, summary, capabilities expansion, and limitations (Part 1 s7.6, FR-F7).
 */

import { h } from "../dom.js";

export function renderCreep(creepData) {
  const panel = h("section", {
    id: "creep-section",
    className: "panel",
    "aria-labelledby": "creep-heading",
  });

  panel.appendChild(
    h("div", { className: "section-label", id: "creep-heading" }, "Permission Creep")
  );

  const creep = creepData || {};

  if (!creep.available) {
    panel.appendChild(
      h(
        "div",
        {
          style: {
            "color": "var(--text-muted)",
            "font-size": "var(--text-sm)",
            "font-style": "italic",
            "padding": "var(--s-3) 0",
          },
        },
        "Baseline not available."
      )
    );
    return panel;
  }

  // Outcome banner with status dot
  let dotColor = "var(--risk-low)";
  if (creep.outcome === "Significant increase in assessed permission exposure") {
    dotColor = "var(--risk-high)";
  } else if (creep.outcome === "Permission changes require review") {
    dotColor = "var(--risk-mid)";
  }

  const outcomeBanner = h(
    "div",
    { className: "creep-outcome-banner" },
    h("span", {
      className: "status-dot",
      style: { "background-color": dotColor },
    }),
    h("span", null, creep.outcome)
  );

  panel.appendChild(outcomeBanner);

  // Summary
  if (creep.summary) {
    panel.appendChild(
      h("p", { style: { "font-size": "var(--text-sm)", "color": "var(--text)" } }, creep.summary)
    );
  }

  // What the added access could allow
  if (creep.could_allow && creep.could_allow.length > 0) {
    const couldAllowBlock = h(
      "div",
      { style: { "display": "flex", "flex-direction": "column", "gap": "var(--s-2)" } },
      h("h4", { className: "section-label" }, "What the added access could allow")
    );
    const list = h("ul", { style: { "padding-left": "var(--s-4)", "font-size": "var(--text-xs)", "color": "var(--text)" } });
    for (const item of creep.could_allow) {
      list.appendChild(h("li", null, item));
    }
    couldAllowBlock.appendChild(list);
    panel.appendChild(couldAllowBlock);
  }

  // Fit with declared purpose
  if (creep.alignment && creep.alignment.text) {
    panel.appendChild(
      h(
        "div",
        { style: { "display": "flex", "flex-direction": "column", "gap": "var(--s-1)" } },
        h("h4", { className: "section-label" }, "Fit with declared purpose"),
        h("p", { style: { "font-size": "var(--text-xs)", "color": "var(--text-muted)" } }, creep.alignment.text)
      )
    );
  }

  // What cannot be concluded (Limitations box - ALWAYS shown)
  const limitationsBox = h(
    "div",
    { className: "limitations-box" },
    h("div", { className: "perm-block-label" }, "What cannot be concluded")
  );

  const limits = creep.limitations && creep.limitations.length > 0
    ? creep.limitations
    : [
        "Manifest lists requested capabilities, not proof of use.",
        "AEGIS does not inspect extension code.",
        "Descriptions are claims, not proof of intent.",
        "Optional permissions require explicit runtime user consent.",
        "Risk scores are heuristics under formula version 1.",
      ];

  const limitList = h("ul", { style: { "padding-left": "var(--s-4)", "display": "flex", "flex-direction": "column", "gap": "var(--s-1)" } });
  for (const l of limits) {
    limitList.appendChild(h("li", null, l));
  }
  limitationsBox.appendChild(limitList);
  panel.appendChild(limitationsBox);

  return panel;
}
