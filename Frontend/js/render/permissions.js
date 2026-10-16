/**
 * AEGIS Permissions Accordion Renderer (render/permissions.js)
 * Visually segregates API, Host, and Optional permissions with expandable details (Part 1 s7.4, FR-F5).
 */

import { h } from "../dom.js";

function renderPermissionGroup(title, items, groupKey) {
  const group = h("div", { className: "perm-group" });
  const count = items.length;

  group.appendChild(
    h("h3", { className: "section-label" }, `${title} (${count})`)
  );

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
    const statusText = perm.status
      ? perm.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
      : "Unknown";

    const summary = h(
      "div",
      { className: "perm-row-summary" },
      h(
        "div",
        { className: "perm-name-status" },
        h("span", { className: "perm-name", dir: "auto" }, perm.name),
        h("span", { className: "perm-status" }, statusText)
      ),
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

    // AEGIS Assessment
    if (perm.assessment || (perm.evidence && perm.evidence.length > 0)) {
      detailsInner.appendChild(
        h("div", { className: "perm-block-label" }, "AEGIS Assessment")
      );
      if (perm.assessment) {
        detailsInner.appendChild(h("div", null, perm.assessment));
      }
      if (perm.evidence && perm.evidence.length > 0) {
        const evList = h("ul", { style: { "padding-left": "var(--s-4)", "margin-top": "var(--s-1)" } });
        for (const ev of perm.evidence) {
          evList.appendChild(h("li", null, ev));
        }
        detailsInner.appendChild(evList);
      }
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

  panel.appendChild(renderPermissionGroup("API Permissions", apiItems, "api"));
  panel.appendChild(renderPermissionGroup("Host Permissions", hostItems, "host"));

  if (optItems.length > 0) {
    panel.appendChild(renderPermissionGroup("Optional Permissions", optItems, "opt"));
  }

  return panel;
}
