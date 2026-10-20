/**
 * AEGIS Permissions Accordion Renderer (render/permissions.js)
 * Visually segregates API, Host, and Optional permissions with expandable details (Part 1 s7.4, FR-F5).
 */

import { h } from "../dom.js";

function humanStatus(status) {
  switch (status) {
    case "justified":
      return { text: "Purpose Aligned", class: "chip-low" };
    case "needs_review":
      return { text: "Review Recommended", class: "chip-mid" };
    case "potentially_excessive":
      return { text: "Broad Website Access", class: "chip-high" };
    case "flagged":
      return { text: "Elevated Capability", class: "chip-high" };
    case "optional":
      return { text: "User-Granted", class: "chip-mid" };
    default:
      return { text: "Uncertain Alignment", class: "chip-mid" };
  }
}

function renderPermissionGroup(title, subtitle, items, groupKey) {
  const group = h("div", { className: "perm-group" });
  const count = items.length;

  const headerBox = h(
    "div",
    { style: { "margin-bottom": "var(--s-1)" } },
    h("h3", { className: "section-label", style: { "margin-bottom": "2px" } }, `${title} (${count})`),
    h("p", { style: { "font-size": "var(--text-xs)", "color": "var(--text-muted)", "margin": "0" } }, subtitle)
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
            "font-size": "var(--text-xs)",
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

  sortedItems.forEach((perm, idx) => {
    const detailId = `perm-detail-${groupKey}-${idx}`;
    const riskWord = (perm.risk_label || "low").toUpperCase();
    const statusMeta = humanStatus(perm.status);

    const nameRow = h(
      "div",
      { style: { "display": "flex", "align-items": "center", "gap": "var(--s-2)", "flex-wrap": "wrap" } },
      h("span", { className: "perm-name", dir: "auto" }, perm.name),
      h("span", { className: `chip ${statusMeta.class}`, style: { "font-size": "10px", "padding": "1px 6px" } }, statusMeta.text)
    );

    const descRow = h(
      "div",
      { className: "perm-plain-desc", style: { "font-size": "var(--text-xs)", "color": "var(--text-muted)", "margin-top": "2px" } },
      perm.allows || "Standard browser access."
    );

    const summary = h(
      "div",
      { className: "perm-row-summary" },
      h("div", { className: "perm-name-status" }, nameRow, descRow),
      h("span", { className: `chip chip-${perm.risk_label || "low"}` }, riskWord)
    );

    const detailsInner = h(
      "div",
      { className: "perm-details-inner" },
      // What it allows
      h("div", { className: "perm-block-label" }, "What it allows"),
      h("div", null, perm.allows || "No specific capability description available."),
      // Why an extension might need it
      h("div", { className: "perm-block-label" }, "Why an extension might need it"),
      h("div", null, perm.legitimate_use || "General extension functionality.")
    );

    // How this was decided (FR-E1)
    const decisionBlock = h("div", {
      className: "perm-decision-block",
      style: {
        "margin-top": "var(--s-2)",
        "padding-top": "var(--s-2)",
        "border-top": "1px solid var(--border)",
      },
    });
    decisionBlock.appendChild(
      h("div", { className: "perm-block-label" }, "How this was decided")
    );

    const ruleReasonRow = h("div", {
      style: {
        "display": "flex",
        "align-items": "baseline",
        "gap": "var(--s-2)",
        "margin-bottom": "var(--s-1)",
      },
    });
    if (perm.rule_id) {
      ruleReasonRow.appendChild(
        h("span", { className: "chip chip-rule" }, `Rule ${perm.rule_id}`)
      );
    }
    const explanationText = perm.reason || perm.assessment || "";
    if (explanationText) {
      ruleReasonRow.appendChild(
        h("span", { style: { "font-size": "var(--text-xs)", "color": "var(--text)" } }, explanationText)
      );
    }
    if (perm.rule_id || explanationText) {
      decisionBlock.appendChild(ruleReasonRow);
    }

    if (perm.evidence && perm.evidence.length > 0) {
      const evList = h("ul", {
        style: {
          "padding-left": "var(--s-4)",
          "margin-top": "var(--s-1)",
          "font-size": "var(--text-xs)",
          "color": "var(--text-muted)",
        },
      });
      for (const ev of perm.evidence) {
        evList.appendChild(h("li", null, ev));
      }
      decisionBlock.appendChild(evList);
    }
    detailsInner.appendChild(decisionBlock);

    // Narrower Alternative
    if (perm.narrower_alternative) {
      detailsInner.appendChild(
        h(
          "div",
          {
            style: {
              "margin-top": "var(--s-2)",
              "font-size": "var(--text-xs)",
              "color": "var(--accent-text)",
            },
          },
          h("span", { style: { "font-weight": "600" } }, "Narrower alternative: "),
          h("span", { className: "mono" }, perm.narrower_alternative)
        )
      );
    }

    // Source link & Review flag
    const metaFooter = h("div", {
      style: {
        "display": "flex",
        "gap": "var(--s-3)",
        "margin-top": "var(--s-2)",
        "font-size": "11px",
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
