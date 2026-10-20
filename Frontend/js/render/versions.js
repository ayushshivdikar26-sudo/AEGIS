/**
 * AEGIS Version Comparison & History Timeline Renderer (render/versions.js)
 * Compares two snapshot versions, highlighting added, broadened, retained, and removed permissions (Part 1 s7.5).
 * Enhanced with C6 font sizes and tokens.
 */

import { h } from "../dom.js";
import { scoreColor, scoreToLevel } from "../lib/risk.js";

/**
 * Parses and compares two version strings according to semantic versioning.
 * Returns > 0 if a > b, < 0 if a < b, 0 if equal.
 */
export function compareSemver(a, b) {
  if (!a && !b) return 0;
  if (!a) return -1;
  if (!b) return 1;

  const pa = String(a).split(/[\.-]/).map((p) => {
    const n = parseInt(p, 10);
    return isNaN(n) ? p : n;
  });
  const pb = String(b).split(/[\.-]/).map((p) => {
    const n = parseInt(p, 10);
    return isNaN(n) ? p : n;
  });

  const maxLen = Math.max(pa.length, pb.length);
  for (let i = 0; i < maxLen; i++) {
    const ai = pa[i] !== undefined ? pa[i] : 0;
    const bi = pb[i] !== undefined ? pb[i] : 0;
    if (typeof ai === "number" && typeof bi === "number") {
      if (ai > bi) return 1;
      if (ai < bi) return -1;
    } else {
      const sa = String(ai);
      const sb = String(bi);
      if (sa > sb) return 1;
      if (sa < sb) return -1;
    }
  }
  return 0;
}

export function renderVersions(versionsData, comparisonData, { onVersionChange }) {
  const panel = h("section", {
    id: "comparison-section",
    className: "panel",
    "aria-labelledby": "comparison-heading",
  });

  panel.appendChild(
    h("div", { className: "section-label", id: "comparison-heading" }, "Version Comparison")
  );

  const rawList = versionsData && versionsData.versions ? versionsData.versions : [];

  if (rawList.length < 2) {
    panel.appendChild(
      h(
        "div",
        {
          style: {
            "color": "var(--text-muted)",
            "font-size": "16px",
            "font-style": "italic",
            "padding": "var(--s-3) 0",
          },
        },
        "Version comparison is unavailable. AEGIS has only one saved snapshot of this extension."
      )
    );

    // If 1 version exists, render single-entry timeline
    if (rawList.length === 1) {
      renderVersionHistoryTimeline(panel, rawList, null);
    }
    return panel;
  }

  // Deduplicate and sort versions descending by semantic version
  const uniqueVersions = [];
  const seenVersions = new Set();
  for (const v of rawList) {
    if (v.version && !seenVersions.has(v.version)) {
      seenVersions.add(v.version);
      uniqueVersions.push(v);
    }
  }

  const versionsList = uniqueVersions.sort((a, b) => compareSemver(b.version, a.version));

  // Determine active versions
  let currentFrom = comparisonData ? comparisonData.version_from : (versionsList[1] ? versionsList[1].version : null);
  let currentTo = comparisonData ? comparisonData.version_to : (versionsList[0] ? versionsList[0].version : null);

  if (!currentFrom && versionsList.length >= 2) {
    currentFrom = versionsList[1].version;
  }
  if (!currentTo && versionsList.length >= 1) {
    currentTo = versionsList[0].version;
  }

  let lastValidOlder = currentFrom;
  let lastValidNewer = currentTo;

  // Version Selectors with C6 font sizes (17px)
  const olderSelect = h("select", {
    id: "version-from-select",
    className: "version-select",
    style: { "font-size": "17px", "padding": "8px 14px", "min-height": "44px" },
    "aria-label": "Select baseline comparison version",
  });

  const newerSelect = h("select", {
    id: "version-to-select",
    className: "version-select",
    style: { "font-size": "17px", "padding": "8px 14px", "min-height": "44px" },
    "aria-label": "Select target comparison version",
  });

  // Validation feedback banner
  const validationNotice = h("div", {
    className: "version-validation-notice",
    role: "alert",
    "aria-live": "polite",
    style: { display: "none" },
  });

  function showNotice(msg) {
    validationNotice.textContent = msg;
    validationNotice.style.display = "block";
  }

  function hideNotice() {
    validationNotice.textContent = "";
    validationNotice.style.display = "none";
  }

  function populateOptions() {
    olderSelect.replaceChildren();
    newerSelect.replaceChildren();

    versionsList.forEach((v) => {
      const optFrom = h("option", { value: v.version }, `v${v.version}`);
      if (v.version === lastValidOlder) optFrom.selected = true;
      if (v.version === lastValidNewer) {
        optFrom.disabled = true;
      }
      olderSelect.appendChild(optFrom);

      const optTo = h("option", { value: v.version }, `v${v.version}`);
      if (v.version === lastValidNewer) optTo.selected = true;
      if (v.version === lastValidOlder) {
        optTo.disabled = true;
      }
      newerSelect.appendChild(optTo);
    });
  }

  populateOptions();

  olderSelect.addEventListener("change", (e) => {
    const fromVal = e.target.value;
    const toVal = newerSelect.value;

    if (fromVal === toVal) {
      showNotice("Select two different versions to compare.");
      e.target.value = lastValidOlder;
      return;
    }

    if (compareSemver(fromVal, toVal) > 0) {
      showNotice(`Baseline (v${fromVal}) is newer than target (v${toVal}). Inverted comparison.`);
    } else {
      hideNotice();
    }

    lastValidOlder = fromVal;
    populateOptions();
    if (typeof onVersionChange === "function") {
      onVersionChange(lastValidOlder, lastValidNewer);
    }
  });

  newerSelect.addEventListener("change", (e) => {
    const toVal = e.target.value;
    const fromVal = olderSelect.value;

    if (toVal === fromVal) {
      showNotice("Select two different versions to compare.");
      e.target.value = lastValidNewer;
      return;
    }

    hideNotice();
    lastValidNewer = toVal;
    populateOptions();
    if (typeof onVersionChange === "function") {
      onVersionChange(lastValidOlder, lastValidNewer);
    }
  });

  const selectorsRow = h(
    "div",
    { className: "version-selectors", style: { "display": "flex", "align-items": "center", "gap": "14px", "margin-bottom": "var(--s-3)" } },
    olderSelect,
    h("span", { className: "version-arrow", style: { "color": "var(--text-muted)", "font-size": "18px" } }, "→"),
    newerSelect
  );

  panel.appendChild(selectorsRow);
  panel.appendChild(validationNotice);

  if (comparisonData) {
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

    // Summary Line (C6: 18px text, 20px bold risk score)
    const summaryLine = h(
      "div",
      {
        style: {
          "font-size": "18px",
          "font-weight": "500",
          "color": "var(--text)",
          "display": "flex",
          "justify-content": "space-between",
          "align-items": "center",
          "flex-wrap": "wrap",
          "gap": "var(--s-2)",
          "padding": "var(--s-3) 0",
          "border-bottom": "1px solid var(--border)",
        },
      },
      h(
        "span",
        null,
        `${totalAdded} added, ${totalRemoved} removed, ${totalRetained} retained, ${totalBroadened} broadened`
      ),
      h("span", { className: "mono", style: { "font-size": "20px", "font-weight": "700", "color": "var(--accent-text)" } }, `Risk score ${comp.score_from} → ${comp.score_to}`)
    );

    panel.appendChild(summaryLine);

    // Plain-Language Overview Card (C6: 22px title, 17px bullets)
    const scoreDiff = comp.score_to - comp.score_from;
    let scoreTrendText = "Exposure score remained constant.";
    let trendColor = "var(--text-muted)";
    if (scoreDiff > 0) {
      scoreTrendText = `Permission exposure increased by +${scoreDiff} points (Risk score: ${comp.score_from} → ${comp.score_to})`;
      trendColor = "var(--risk-high)";
    } else if (scoreDiff < 0) {
      scoreTrendText = `Permission exposure decreased by ${Math.abs(scoreDiff)} points (Risk score: ${comp.score_from} → ${comp.score_to})`;
      trendColor = "var(--risk-low)";
    }

    const overviewCard = h(
      "div",
      { className: "version-overview-card", style: { "margin-top": "var(--s-3)" } },
      h(
        "div",
        { className: "version-overview-title", style: { "font-size": "22px", "font-weight": "700", "color": "var(--text)", "margin-bottom": "6px" } },
        `What Changed from v${currentFrom} to v${currentTo}?`
      ),
      h(
        "div",
        { className: "version-overview-trend", style: { "color": trendColor, "font-size": "17px", "font-weight": "600", "margin-bottom": "10px" } },
        scoreTrendText
      )
    );

    const changesList = h("ul", { className: "version-overview-list", style: { "font-size": "17px", "line-height": "1.5", "display": "flex", "flex-direction": "column", "gap": "8px" } });

    if (totalAdded > 0) {
      const addedNames = [...apiAdded.map((a) => a.name), ...hostAdded.map((h) => h.name)].join(", ");
      changesList.appendChild(
        h(
          "li",
          null,
          h("strong", null, "New Capabilities Added: "),
          `This update introduces ${totalAdded} new permission(s): `,
          h("span", { className: "mono", style: { "color": "var(--accent-text)" } }, addedNames),
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

    // Group Diff Rows (C6: 18px mono rows with 14px badges)
    function renderGroupDiff(title, group, broadened = []) {
      const cont = h("div", { style: { "display": "flex", "flex-direction": "column", "gap": "var(--s-2)", "margin-top": "var(--s-3)" } });
      cont.appendChild(h("h4", { className: "section-label", style: { "font-size": "14px" } }, title));

      // 1. Added
      for (const item of group.added || []) {
        const riskLabel = (item.risk_label || "mid").toLowerCase();
        const chipClass = (riskLabel === "critical" || riskLabel === "high") ? `chip chip-${riskLabel}` : "chip chip-mid";
        const tagText = (riskLabel === "critical" || riskLabel === "high") ? `Added (${riskLabel.toUpperCase()})` : "Added";
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-added", style: { "font-size": "18px", "padding": "12px 16px" } },
            h("span", { className: "mono", dir: "auto" }, `+ ${item.name}`),
            h("span", { className: chipClass, style: { "font-size": "14px" } }, tagText)
          )
        );
      }

      // 2. Broadened
      for (const b of broadened) {
        const broadenedCol = h("div", { style: { "display": "flex", "flex-direction": "column", "gap": "2px" } },
          h("span", { className: "mono", dir: "auto" }, `${b.from_pattern} → ${b.to_pattern}`)
        );
        if (b.explanation) {
          broadenedCol.appendChild(
            h("span", { style: { "font-size": "15px", "color": "var(--text-muted)", "font-weight": "normal", "font-family": "system-ui, sans-serif" } }, b.explanation)
          );
        }
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-broadened", style: { "font-size": "18px", "padding": "12px 16px" } },
            broadenedCol,
            h("span", { className: "chip chip-high", style: { "font-size": "14px" } }, "Broadened Scope")
          )
        );
      }

      // 3. Retained
      for (const item of group.retained || []) {
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-retained", style: { "font-size": "18px", "padding": "12px 16px" } },
            h("span", { className: "mono", dir: "auto" }, h("span", { className: "retained-dot" }), item.name),
            h("span", { style: { "color": "var(--text-muted)", "font-size": "14px" } }, "Retained")
          )
        );
      }

      // 4. Removed
      for (const item of group.removed || []) {
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-removed", style: { "font-size": "18px", "padding": "12px 16px" } },
            h("span", { className: "mono", dir: "auto" }, `- ${item.name}`),
            h("span", { style: { "color": "var(--text-muted)", "font-size": "14px" } }, "Removed")
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
  }

  // Render Version History Timeline Table (C6: 14px caps header, 17px rows, 20px risk numbers)
  renderVersionHistoryTimeline(panel, versionsList, (olderV, newerV) => {
    lastValidOlder = olderV;
    lastValidNewer = newerV;
    populateOptions();
    if (typeof onVersionChange === "function") {
      onVersionChange(olderV, newerV);
    }
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  return panel;
}

/**
 * Renders an append-only Version History Timeline table.
 * C6: Header 14px caps, rows 17px, risk numbers 20px.
 */
function renderVersionHistoryTimeline(container, versionsList, onDiffClick) {
  const timelineCont = h("div", { className: "version-timeline", style: { "margin-top": "var(--s-4)" } });
  timelineCont.appendChild(
    h("h4", { className: "section-label", style: { "font-size": "14px", "margin-bottom": "var(--s-2)" } }, "Version History Timeline")
  );

  const table = h(
    "table",
    { className: "timeline-table" },
    h(
      "thead",
      null,
      h(
        "tr",
        null,
        h("th", { style: { "font-size": "14px", "text-transform": "uppercase", "letter-spacing": "0.05em" } }, "Version"),
        h("th", { style: { "font-size": "14px", "text-transform": "uppercase", "letter-spacing": "0.05em" } }, "Captured"),
        h("th", { style: { "font-size": "14px", "text-transform": "uppercase", "letter-spacing": "0.05em" } }, "Assessed Risk"),
        h("th", { style: { "font-size": "14px", "text-transform": "uppercase", "letter-spacing": "0.05em" } }, "Action")
      )
    )
  );

  const tbody = h("tbody", null);

  versionsList.forEach((v, index) => {
    const isLatest = index === 0;
    const olderVersion = versionsList[index + 1]?.version;

    const versionCol = h(
      "td",
      { style: { "font-size": "17px" } },
      h("span", { className: "mono", style: { "font-weight": "600", "color": "var(--text)" } }, v.version),
      isLatest ? h("span", { className: "chip", style: { "margin-left": "var(--s-2)", "background": "rgba(37,99,235,0.2)", "color": "var(--accent-text)", "font-size": "12px" } }, "Latest") : null,
      v.is_suspicious ? h("span", { className: "chip chip-high", style: { "margin-left": "var(--s-2)", "font-size": "12px" } }, "Hash Mismatch") : null
    );

    const dateStr = v.released || (v.captured_at ? v.captured_at.slice(0, 10) : "Recorded");
    const dateCol = h("td", { style: { "color": "var(--text-muted)", "font-size": "17px" } }, dateStr);

    const score = v.risk_score !== undefined ? v.risk_score : 0;
    const level = scoreToLevel(score);
    const color = scoreColor(score);
    const scoreCol = h(
      "td",
      { style: { "font-size": "17px" } },
      h("span", { className: "mono", style: { "color": color, "font-size": "20px", "font-weight": "700" } }, `${score} `),
      h("span", { style: { "font-size": "13px", "text-transform": "uppercase", "color": color, "font-weight": "600" } }, `[${level}]`)
    );

    const actionCol = h("td", null);
    if (olderVersion && onDiffClick) {
      const diffBtn = h(
        "button",
        {
          type: "button",
          className: "timeline-btn-diff",
          style: { "font-size": "15px", "padding": "6px 12px" },
          title: `Compare v${olderVersion} to v${v.version}`,
        },
        "What changed?"
      );
      diffBtn.addEventListener("click", () => {
        onDiffClick(olderVersion, v.version);
      });
      actionCol.appendChild(diffBtn);
    } else {
      actionCol.appendChild(
        h("span", { style: { "color": "var(--text-muted)", "font-style": "italic", "font-size": "14px" } }, "Baseline")
      );
    }

    tbody.appendChild(h("tr", null, versionCol, dateCol, scoreCol, actionCol));
  });

  table.appendChild(tbody);
  timelineCont.appendChild(table);
  container.appendChild(timelineCont);
}
