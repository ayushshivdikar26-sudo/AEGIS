/**
 * AEGIS Permission Creep Renderer (render/creep.js)
 * Displays creep classification, summary, capabilities expansion, and limitations (Part 1 s7.6, FR-F7, Milestone 2 C6).
 */

import { h } from "../dom.js";

export function renderCreep(creepData) {
  const panel = h("section", {
    id: "creep-section",
    className: "panel",
    "aria-labelledby": "creep-heading",
  });

  panel.appendChild(
    h(
      "h2",
      {
        className: "section-title",
        id: "creep-heading",
        style: {
          "font-size": "var(--fs-detail-lg, 22px)",
          "font-weight": "700",
          "color": "var(--text)",
          "margin": "0 0 var(--s-3) 0",
        },
      },
      "Permission Creep"
    )
  );

  const creep = creepData || {};

  if (!creep.available) {
    panel.appendChild(
      h(
        "div",
        {
          style: {
            "color": "var(--text-muted)",
            "font-size": "var(--fs-detail-base, 16px)",
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
    {
      className: "creep-outcome-banner",
      style: {
        "display": "flex",
        "align-items": "center",
        "gap": "10px",
        "font-size": "var(--fs-detail-xl, 24px)",
        "font-weight": "700",
        "color": "var(--text)",
      },
    },
    h("span", {
      className: "status-dot",
      style: {
        "background-color": dotColor,
        "width": "12px",
        "height": "12px",
        "border-radius": "50%",
        "display": "inline-block",
        "flex-shrink": "0",
      },
    }),
    h("span", null, creep.outcome)
  );

  let outcomeSubtitle = "This update maintains a consistent permission footprint.";
  if (creep.outcome === "Significant increase in assessed permission exposure") {
    outcomeSubtitle = "This update meaningfully expands what data or websites this extension can access on your computer.";
  } else if (creep.outcome === "Permission changes require review") {
    outcomeSubtitle = "Permissions were modified in ways that warrant user attention.";
  }

  const outcomeBlock = h(
    "div",
    {
      className: "creep-outcome-block",
      style: {
        "display": "flex",
        "flex-direction": "column",
        "gap": "var(--s-2)",
        "margin-bottom": "var(--s-2)",
      },
    },
    outcomeBanner,
    h(
      "div",
      {
        style: {
          "font-size": "17px",
          "color": "var(--text-muted)",
          "padding-left": "22px",
          "line-height": "1.5",
        },
      },
      outcomeSubtitle
    )
  );

  panel.appendChild(outcomeBlock);

  // Summary
  if (creep.summary) {
    panel.appendChild(
      h(
        "p",
        {
          style: {
            "font-size": "var(--fs-detail-md, 18px)",
            "color": "var(--text)",
            "line-height": "1.5",
            "margin": "var(--s-2) 0",
          },
        },
        creep.summary
      )
    );
  }

  // What the added access could allow
  if (creep.could_allow && creep.could_allow.length > 0) {
    const couldAllowBlock = h(
      "div",
      {
        style: {
          "display": "flex",
          "flex-direction": "column",
          "gap": "var(--s-2)",
          "margin-top": "var(--s-2)",
        },
      },
      h(
        "h4",
        {
          className: "section-label",
          style: {
            "font-size": "14px",
            "font-weight": "700",
            "text-transform": "uppercase",
            "letter-spacing": "0.06em",
            "color": "var(--text-muted)",
          },
        },
        "What the added access could allow"
      )
    );
    const list = h("ul", {
      style: {
        "padding-left": "var(--s-4)",
        "font-size": "17px",
        "color": "var(--text)",
        "display": "flex",
        "flex-direction": "column",
        "gap": "6px",
        "line-height": "1.5",
      },
    });
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
        {
          style: {
            "display": "flex",
            "flex-direction": "column",
            "gap": "var(--s-2)",
            "margin-top": "var(--s-2)",
          },
        },
        h(
          "h4",
          {
            className: "section-label",
            style: {
              "font-size": "14px",
              "font-weight": "700",
              "text-transform": "uppercase",
              "letter-spacing": "0.06em",
              "color": "var(--text-muted)",
            },
          },
          "Fit with declared purpose"
        ),
        h(
          "p",
          {
            style: {
              "font-size": "var(--fs-detail-base, 16px)",
              "color": "var(--text)",
              "line-height": "1.5",
            },
          },
          creep.alignment.text
        )
      )
    );
  }

  // What cannot be concluded (Limitations box - ALWAYS shown)
  const limitationsBox = h(
    "div",
    {
      className: "limitations-box",
      style: {
        "background-color": "var(--surface-2)",
        "border": "1px solid var(--border)",
        "border-radius": "var(--radius-sm)",
        "padding": "var(--s-4)",
        "margin-top": "var(--s-3)",
      },
    },
    h(
      "div",
      {
        className: "perm-block-label",
        style: {
          "font-size": "14px",
          "font-weight": "700",
          "text-transform": "uppercase",
          "letter-spacing": "0.06em",
          "color": "var(--text-muted)",
          "margin-bottom": "var(--s-2)",
        },
      },
      "What cannot be concluded"
    )
  );

  const limits =
    creep.limitations && creep.limitations.length > 0
      ? creep.limitations
      : [
          "Manifest lists requested capabilities, not proof of use.",
          "AEGIS does not inspect extension code.",
          "Descriptions are claims, not proof of intent.",
          "Optional permissions require explicit runtime user consent.",
          "Risk scores are heuristics under formula version 1.",
        ];

  const limitList = h("ul", {
    style: {
      "padding-left": "var(--s-4)",
      "display": "flex",
      "flex-direction": "column",
      "gap": "var(--s-2)",
      "font-size": "var(--fs-detail-base, 16px)",
      "color": "var(--text)",
      "line-height": "1.5",
    },
  });
  for (const l of limits) {
    limitList.appendChild(h("li", null, l));
  }
  limitationsBox.appendChild(limitList);
  panel.appendChild(limitationsBox);

  return panel;
}
