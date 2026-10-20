/**
 * AEGIS Permissions Section Renderer (render/permissions.js)
 * Implements categorised accordion (API, Host, Optional) with weights,
 * plain-language decision explanations (without internal rule IDs - C7),
 * and enhanced typography tokens (C6).
 */

import { h } from "../dom.js";

function humanStatus(status) {
  switch (status) {
    case "certain_positive":
      return { text: "PURPOSE ALIGNED", class: "chip-low" };
    case "uncertain":
      return { text: "UNCERTAIN ALIGNMENT", class: "chip-mid" };
    case "certain_negative":
      return { text: "EXCESS CAPABILITY", class: "chip-high" };
    default:
      return { text: "EVALUATING", class: "chip-neutral" };
  }
}

function renderPermissionGroup(title, subtitle, items, groupKey) {
  const group = h("div", { className: "perm-group" });
  const count = items ? items.length : 0;

  const headerBox = h(
    "div",
    { style: { "margin-bottom": "var(--s-1)", "margin-top": "var(--s-2)" } },
    h("h3", { className: "section-label", style: { "font-size": "14px", "margin-bottom": "4px" } }, `${title} (${count})`),
    h("p", { style: { "font-size": "14px", "color": "var(--text-muted)", "margin": "0" } }, subtitle)
  );
  group.appendChild(headerBox);

  if (count === 0) {
    group.appendChild(
      h(
        "div",
        {
          style: {
            "padding": "var(--s-3)",
            "color": "var(--text-muted)",
            "font-size": "14px",
            "font-style": "italic",
          },
        },
        "No permissions of this type."
      )
    );
    return group;
  }

  // Sort by weight descending, then name
  const sortedItems = [...items].sort((a, b) => {
    if (b.weight !== a.weight) {
      return b.weight - a.weight;
    }
    return a.name.localeCompare(b.name);
  });

  const isHostGroup = groupKey === "host";

  sortedItems.forEach((perm, idx) => {
    const detailId = `perm-detail-${groupKey}-${idx}`;
    const riskWord = (perm.risk_label || "low").toUpperCase();
    const statusMeta = humanStatus(perm.status);

    const nameSize = isHostGroup ? "17px" : "19px";
    const nameRow = h(
      "div",
      { style: { "display": "flex", "align-items": "center", "gap": "var(--s-2)", "flex-wrap": "wrap" } },
      h("span", { className: "perm-name", style: { "font-size": nameSize }, dir: "auto" }, perm.name),
      h("span", { className: `chip ${statusMeta.class}`, style: { "font-size": "13px", "padding": "2px 8px" } }, statusMeta.text)
    );

    const descRow = h(
      "div",
      { className: "perm-plain-desc", style: { "font-size": "16px", "color": "var(--text-muted)", "margin-top": "4px" } },
      perm.allows || "Standard browser access."
    );

    const summary = h(
      "div",
      { className: "perm-row-summary" },
      h("div", { className: "perm-name-status" }, nameRow, descRow),
      h("span", { className: `chip chip-${perm.risk_label || "low"}`, style: { "font-size": "14px", "font-weight": "700" } }, riskWord)
    );

    const detailsInner = h(
      "div",
      { className: "perm-details-inner", style: { "font-size": "16px" } },
      // What it allows
      h("div", { className: "perm-block-label", style: { "font-size": "14px" } }, "What it allows"),
      h("div", { style: { "font-size": "16px", "color": "var(--text)" } }, perm.allows || "No specific capability description available."),
      // Why an extension might need it
      h("div", { className: "perm-block-label", style: { "font-size": "14px" } }, "Why an extension might need it"),
      h("div", { style: { "font-size": "16px", "color": "var(--text)" } }, perm.legitimate_use || "General extension functionality.")
    );

    // How this was decided (C7: NO RULE IDs, plain-language full-width explanation at 16px)
    const explanationText = perm.reason || perm.assessment || "";
    if (explanationText || (perm.evidence && perm.evidence.length > 0)) {
      const decisionBlock = h("div", {
        className: "perm-decision-block",
        style: {
          "margin-top": "var(--s-3)",
          "padding-top": "var(--s-3)",
          "border-top": "1px solid var(--border)",
        },
      });
      decisionBlock.appendChild(
        h("div", { className: "perm-block-label", style: { "font-size": "14px", "margin-bottom": "var(--s-2)" } }, "How this was decided")
      );

      if (explanationText) {
        decisionBlock.appendChild(
          h(
            "p",
            {
              className: "perm-decision-text",
              style: {
                "font-size": "16px",
                "color": "var(--text)",
                "line-height": "1.5",
                "margin-bottom": "var(--s-2)",
              },
            },
            explanationText
          )
        );
      }

      if (perm.evidence && perm.evidence.length > 0) {
        const evList = h("ul", {
          style: {
            "padding-left": "var(--s-4)",
            "margin-top": "var(--s-1)",
            "font-size": "15px",
            "color": "var(--text-muted)",
          },
        });
        for (const ev of perm.evidence) {
          evList.appendChild(h("li", null, ev));
        }
        decisionBlock.appendChild(evList);
      }
      detailsInner.appendChild(decisionBlock);
    }

    // Narrower Alternative
    if (perm.narrower_alternative) {
      detailsInner.appendChild(
        h(
          "div",
          {
            style: {
              "margin-top": "var(--s-3)",
              "font-size": "15px",
              "color": "var(--accent-text)",
            },
          },
          h("span", { style: { "font-weight": "600" } }, "Documented narrower alternative: "),
          h("span", { className: "mono" }, perm.narrower_alternative)
        )
      );
    }

    // Documentation Link & Review Flag
    const metaFooter = h("div", {
      style: {
        "display": "flex",
        "gap": "var(--s-3)",
        "margin-top": "var(--s-3)",
        "font-size": "14px",
      },
    });

    if (perm.source_url) {
      metaFooter.appendChild(
        h(
          "a",
          {
            href: perm.source_url,
            target: "_blank",
            rel: "noopener noreferrer",
            style: { "color": "var(--accent-text)" },
          },
          "Documentation"
        )
      );
    }

    if (perm.reviewed === false) {
      metaFooter.appendChild(
        h("span", { style: { "color": "var(--risk-mid)" } }, "Weight not yet reviewed")
      );
    }

    detailsInner.appendChild(metaFooter);

    const details = h(
      "div",
      {
        id: detailId,
        className: "perm-details",
        "data-expanded": "false",
      },
      detailsInner
    );

    const rowBtn = h(
      "button",
      {
        type: "button",
        className: "perm-row-btn",
        style: { "padding": "16px 20px" },
        "aria-expanded": "false",
        "aria-controls": detailId,
      },
      summary,
      details
    );

    rowBtn.addEventListener("click", () => {
      const isExpanded = rowBtn.getAttribute("aria-expanded") === "true";
      rowBtn.setAttribute("aria-expanded", String(!isExpanded));
      details.setAttribute("data-expanded", String(!isExpanded));
    });

    group.appendChild(rowBtn);
  });

  return group;
}

export function renderPermissions(permissionsData) {
  const panel = h("section", {
    id: "permissions-section",
    className: "panel",
    "aria-labelledby": "permissions-heading",
  });

  panel.appendChild(
    h("div", { className: "section-label", id: "permissions-heading" }, "Permissions")
  );

  const data = permissionsData || {};
  const apiItems = data.api || [];
  const hostItems = data.host || [];
  const optItems = data.optional || [];

  panel.appendChild(
    renderPermissionGroup(
      "Browser Capabilities (API Permissions)",
      "Special browser tools and features this extension is allowed to use.",
      apiItems,
      "api"
    )
  );
  panel.appendChild(
    renderPermissionGroup(
      "Website Access (Host Permissions)",
      "Websites this extension can read or modify while you browse.",
      hostItems,
      "host"
    )
  );

  if (optItems.length > 0) {
    panel.appendChild(
      renderPermissionGroup(
        "Optional Capabilities",
        "Permissions enabled only when you explicitly grant consent.",
        optItems,
        "opt"
      )
    );
  }

  return panel;
}
