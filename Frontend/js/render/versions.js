/**
 * AEGIS Version Comparison Renderer (render/versions.js)
 * Compares two snapshot versions, highlighting added, broadened, retained, and removed permissions (Part 1 s7.5).
 */

import { h } from "../dom.js";

export function renderVersions(versionsData, comparisonData, { onVersionChange }) {
  const panel = h("section", {
    id: "comparison-section",
    className: "panel",
    "aria-labelledby": "comparison-heading",
  });

  panel.appendChild(
    h("div", { className: "section-label", id: "comparison-heading" }, "Version Comparison")
  );

  const versionsList = versionsData && versionsData.versions ? versionsData.versions : [];

  if (versionsList.length < 2) {
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
        "Version comparison is unavailable. AEGIS has only one saved snapshot of this extension."
      )
    );
    return panel;
  }

  // Version Selectors
  const olderSelect = h("select", { className: "version-select", "aria-label": "Older version" });
  const newerSelect = h("select", { className: "version-select", "aria-label": "Newer version" });

  const currentFrom = comparisonData ? comparisonData.from : versionsList[1]?.version;
  const currentTo = comparisonData ? comparisonData.to : versionsList[0]?.version;

  versionsList.forEach((v) => {
    const optOld = h("option", { value: v.version }, v.version);
    if (v.version === currentFrom) optOld.selected = true;
    olderSelect.appendChild(optOld);

    const optNew = h("option", { value: v.version }, v.version);
    if (v.version === currentTo) optNew.selected = true;
    newerSelect.appendChild(optNew);
  });

  function handleSelect() {
    const fromVal = olderSelect.value;
    const toVal = newerSelect.value;
    if (fromVal === toVal) {
      alert("Older and Newer versions must be different.");
      return;
    }
    onVersionChange(fromVal, toVal);
  }

  olderSelect.addEventListener("change", handleSelect);
  newerSelect.addEventListener("change", handleSelect);

  const selectorsRow = h(
    "div",
    { className: "version-selectors" },
    olderSelect,
    h("span", { className: "version-arrow", style: { "color": "var(--text-muted)" } }, "->"),
    newerSelect
  );

  panel.appendChild(selectorsRow);

  if (!comparisonData) {
    return panel;
  }

  const comp = comparisonData;
  const apiAdded = (comp.api && comp.api.added) || [];
  const apiRemoved = (comp.api && comp.api.removed) || [];
  const apiRetained = (comp.api && comp.api.retained) || [];

  const hostAdded = (comp.host && comp.host.added) || [];
  const hostRemoved = (comp.host && comp.host.removed) || [];
  const hostRetained = (comp.host && comp.host.retained) || [];
  const hostBroadened = (comp.host && comp.host.broadened) || [];

  const totalAdded = apiAdded.length + hostAdded.length;
  const totalRemoved = apiRemoved.length + hostRemoved.length;
  const totalRetained = apiRetained.length + hostRetained.length;
  const totalBroadened = hostBroadened.length;

  // Summary Line
  const summaryLine = h(
    "div",
    {
      style: {
        "font-size": "var(--text-sm)",
        "font-weight": "600",
        "color": "var(--text)",
        "display": "flex",
        "justify-content": "space-between",
        "flex-wrap": "wrap",
        "gap": "var(--s-2)",
        "padding": "var(--s-2) 0",
        "border-bottom": "1px solid var(--border)",
      },
    },
    h("span", null, `${totalAdded} added, ${totalRemoved} removed, ${totalRetained} retained, ${totalBroadened} broadened`),
    h("span", { className: "mono" }, `Risk score ${comp.score_from} -> ${comp.score_to}`)
  );

  panel.appendChild(summaryLine);

  // Plain-Language Overview Card for Non-Technical Audiences
  const scoreDiff = comp.score_to - comp.score_from;
  let scoreTrendText = "Exposure score remained constant.";
  let trendColor = "var(--text-muted)";
  if (scoreDiff > 0) {
    scoreTrendText = `Permission exposure increased by +${scoreDiff} points (Risk score: ${comp.score_from} -> ${comp.score_to})`;
    trendColor = "var(--risk-high)";
  } else if (scoreDiff < 0) {
    scoreTrendText = `Permission exposure decreased by ${Math.abs(scoreDiff)} points (Risk score: ${comp.score_from} -> ${comp.score_to})`;
    trendColor = "var(--risk-low)";
  }

  const overviewCard = h(
    "div",
    { className: "version-overview-card" },
    h(
      "div",
      { className: "version-overview-title" },
      h("strong", null, `What Changed from v${currentFrom} to v${currentTo}?`)
    ),
    h(
      "div",
      { className: "version-overview-trend", style: { "color": trendColor } },
      scoreTrendText
    )
  );

  const changesList = h("ul", { className: "version-overview-list" });

  if (totalAdded > 0) {
    const addedNames = [...apiAdded.map((a) => a.name), ...hostAdded.map((h) => h.name)].join(", ");
    changesList.appendChild(
      h(
        "li",
        null,
        h("strong", null, "New Capabilities Added: "),
        `This update introduces ${totalAdded} new permission(s): `,
        h("span", { className: "mono" }, addedNames),
        ". Review is suggested to verify that these new powers align with the extension's stated purpose."
      )
    );
  }

  if (totalBroadened > 0) {
    changesList.appendChild(
      h(
        "li",
        null,
        h("strong", null, "Website Access Broadened: "),
        `Host access was widened across ${totalBroadened} pattern(s). The extension can now read or change data on more websites than before.`
      )
    );
  }

  if (totalRemoved > 0) {
    changesList.appendChild(
      h(
        "li",
        null,
        h("strong", null, "Permissions Removed: "),
        `This update removed ${totalRemoved} previously granted permission(s), reducing the exposure footprint.`
      )
    );
  }

  if (totalAdded === 0 && totalBroadened === 0 && totalRemoved === 0) {
    changesList.appendChild(
      h(
        "li",
        null,
        "No permission or website access changes were detected between these two releases."
      )
    );
  }

  overviewCard.appendChild(changesList);
  panel.appendChild(overviewCard);

  // Helper to render diff items
  function renderGroupDiff(title, group, broadened = []) {
    const cont = h("div", { style: { "display": "flex", "flex-direction": "column", "gap": "var(--s-2)" } });
    cont.appendChild(h("h4", { className: "section-label" }, title));

    // 1. Added
    for (const item of group.added || []) {
      const riskLabel = (item.risk_label || "mid").toLowerCase();
      const chipClass = (riskLabel === "critical" || riskLabel === "high") ? `chip chip-${riskLabel}` : "chip chip-mid";
      const tagText = (riskLabel === "critical" || riskLabel === "high") ? `Added (${riskLabel.toUpperCase()})` : "Added";
      cont.appendChild(
        h(
          "div",
          { className: "diff-row diff-added" },
          h("span", { dir: "auto" }, `+ ${item.name}`),
          h("span", { className: chipClass }, tagText)
        )
      );
    }

    // 2. Broadened
    for (const b of broadened) {
      const broadenedCol = h("div", { style: { "display": "flex", "flex-direction": "column", "gap": "2px" } },
        h("span", { dir: "auto" }, `${b.from_pattern} -> ${b.to_pattern}`)
      );
      if (b.explanation) {
        broadenedCol.appendChild(
          h("span", { style: { "font-size": "var(--text-xs)", "color": "var(--text-muted)", "font-weight": "normal", "font-family": "system-ui, sans-serif" } }, b.explanation)
        );
      }
      cont.appendChild(
        h(
          "div",
          { className: "diff-row diff-broadened" },
          broadenedCol,
          h("span", { className: "chip chip-high" }, "Broadened Scope")
        )
      );
    }

    // 3. Retained
    for (const item of group.retained || []) {
      cont.appendChild(
        h(
          "div",
          { className: "diff-row diff-retained" },
          h("span", { dir: "auto" }, h("span", { className: "retained-dot" }), item.name),
          h("span", { style: { "color": "var(--text-muted)", "font-size": "var(--text-xs)" } }, "Retained")
        )
      );
    }

    // 4. Removed
    for (const item of group.removed || []) {
      cont.appendChild(
        h(
          "div",
          { className: "diff-row diff-removed" },
          h("span", { dir: "auto" }, `- ${item.name}`),
          h("span", { style: { "color": "var(--text-muted)", "font-size": "var(--text-xs)" } }, "Removed")
        )
      );
    }

    return cont;
  }

  if (comp.api) {
    panel.appendChild(renderGroupDiff("API Permissions", comp.api));
  }
  if (comp.host) {
    panel.appendChild(renderGroupDiff("Host Permissions", comp.host, hostBroadened));
  }

  return panel;
}
