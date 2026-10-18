/**
 * AEGIS Version Comparison & History Timeline Renderer (render/versions.js)
 * Compares two snapshot versions, highlighting added, broadened, retained, and removed permissions (Part 1 s7.5).
 * Implements Milestone 1b (mutual option disabling, revert on invalid, semver sorting)
 * and Milestone 1c (historical timeline with "What changed?" drill-down).
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
            "font-size": "var(--text-sm)",
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

  // Sort versions semantically descending (newest version first)
  const versionsList = [...rawList].sort((a, b) => compareSemver(b.version, a.version));

  // Default selection: older = second-latest, newer = latest
  const defaultFrom = versionsList[1]?.version;
  const defaultTo = versionsList[0]?.version;

  let currentFrom = comparisonData && comparisonData.from ? comparisonData.from : defaultFrom;
  let currentTo = comparisonData && comparisonData.to ? comparisonData.to : defaultTo;

  // Validate that currentFrom < currentTo
  if (compareSemver(currentFrom, currentTo) >= 0) {
    currentFrom = defaultFrom;
    currentTo = defaultTo;
  }

  let lastValidOlder = currentFrom;
  let lastValidNewer = currentTo;

  // Version Selectors
  const olderSelect = h("select", { className: "version-select", "aria-label": "Older version" });
  const newerSelect = h("select", { className: "version-select", "aria-label": "Newer version" });

  // Inline validation notice (replaces native alert())
  const validationNotice = h("div", {
    className: "version-validation-notice is-hidden",
  });

  function showNotice(msg) {
    validationNotice.textContent = msg;
    validationNotice.classList.remove("is-hidden");
  }

  function hideNotice() {
    validationNotice.classList.add("is-hidden");
    validationNotice.textContent = "";
  }

  function populateOptions() {
    olderSelect.replaceChildren();
    newerSelect.replaceChildren();

    versionsList.forEach((v) => {
      // In older select: cannot be newer than or equal to current newer
      const isOlderDisabled = compareSemver(v.version, lastValidNewer) >= 0;
      const optOld = h(
        "option",
        {
          value: v.version,
          disabled: isOlderDisabled,
        },
        v.version + (v.is_suspicious ? " ⚠️ (rev)" : "")
      );
      if (v.version === lastValidOlder) optOld.selected = true;
      olderSelect.appendChild(optOld);

      // In newer select: cannot be older than or equal to current older
      const isNewerDisabled = compareSemver(v.version, lastValidOlder) <= 0;
      const optNew = h(
        "option",
        {
          value: v.version,
          disabled: isNewerDisabled,
        },
        v.version + (v.is_suspicious ? " ⚠️ (rev)" : "")
      );
      if (v.version === lastValidNewer) optNew.selected = true;
      newerSelect.appendChild(optNew);
    });
  }

  populateOptions();

  olderSelect.addEventListener("change", () => {
    const fromVal = olderSelect.value;
    const toVal = lastValidNewer;

    if (fromVal === toVal || compareSemver(fromVal, toVal) >= 0) {
      showNotice("Older version must be an earlier version than newer version. Selection reverted.");
      olderSelect.value = lastValidOlder;
      return;
    }

    hideNotice();
    lastValidOlder = fromVal;
    populateOptions();
    if (typeof onVersionChange === "function") {
      onVersionChange(lastValidOlder, lastValidNewer);
    }
  });

  newerSelect.addEventListener("change", () => {
    const fromVal = lastValidOlder;
    const toVal = newerSelect.value;

    if (fromVal === toVal || compareSemver(fromVal, toVal) >= 0) {
      showNotice("Newer version must be a later version than older version. Selection reverted.");
      newerSelect.value = lastValidNewer;
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
    { className: "version-selectors" },
    olderSelect,
    h("span", { className: "version-arrow", style: { "color": "var(--text-muted)" } }, "->"),
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
      h(
        "span",
        null,
        `${totalAdded} added, ${totalRemoved} removed, ${totalRetained} retained, ${totalBroadened} broadened`
      ),
      h("span", { className: "mono" }, `Risk score ${comp.score_from} -> ${comp.score_to}`)
    );

    panel.appendChild(summaryLine);

    // Helper to render diff items
    function renderGroupDiff(title, group, broadened = []) {
      const cont = h("div", { style: { "display": "flex", "flex-direction": "column", "gap": "var(--s-2)" } });
      cont.appendChild(h("h4", { className: "section-label" }, title));

      // 1. Added
      for (const item of group.added || []) {
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-added" },
            h("span", { dir: "auto" }, `+ ${item.name}`),
            h("span", { className: "chip chip-mid" }, "Added")
          )
        );
      }

      // 2. Broadened
      for (const b of broadened) {
        cont.appendChild(
          h(
            "div",
            { className: "diff-row diff-broadened" },
            h("span", { dir: "auto" }, `${b.from_pattern} -> ${b.to_pattern}`),
            h("span", { className: "chip chip-mid" }, "Broadened")
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
  }

  // Render Version History Timeline
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
 * Renders an append-only Version History Timeline table with captured dates,
 * risk scores, suspicious indicators, and a "What changed?" drill-down action (Milestone 1c).
 */
function renderVersionHistoryTimeline(container, versionsList, onDiffClick) {
  const timelineCont = h("div", { className: "version-timeline" });
  timelineCont.appendChild(
    h("h4", { className: "section-label", style: { "margin-bottom": "var(--s-2)" } }, "Version History Timeline")
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
        h("th", null, "Version"),
        h("th", null, "Captured"),
        h("th", null, "Assessed Risk"),
        h("th", null, "Action")
      )
    )
  );

  const tbody = h("tbody", null);

  versionsList.forEach((v, index) => {
    const isLatest = index === 0;
    const olderVersion = versionsList[index + 1]?.version;

    const versionCol = h(
      "td",
      null,
      h("span", { className: "mono", style: { "font-weight": "600", "color": "var(--text)" } }, v.version),
      isLatest ? h("span", { className: "chip", style: { "margin-left": "var(--s-2)", "background": "rgba(37,99,235,0.2)", "color": "var(--accent-text)" } }, "Latest") : null,
      v.is_suspicious ? h("span", { className: "chip chip-high", style: { "margin-left": "var(--s-2)" } }, "Hash Mismatch") : null
    );

    const dateStr = v.released || (v.captured_at ? v.captured_at.slice(0, 10) : "Recorded");
    const dateCol = h("td", { style: { "color": "var(--text-muted)" } }, dateStr);

    const score = v.risk_score !== undefined ? v.risk_score : 0;
    const level = scoreToLevel(score);
    const color = scoreColor(score);
    const scoreCol = h(
      "td",
      null,
      h("span", { className: "mono", style: { "color": color, "font-weight": "600" } }, `${score} `),
      h("span", { style: { "font-size": "10px", "text-transform": "uppercase", "color": color } }, `[${level}]`)
    );

    const actionCol = h("td", null);
    if (olderVersion && onDiffClick) {
      const diffBtn = h(
        "button",
        {
          type: "button",
          className: "timeline-btn-diff",
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
        h("span", { style: { "color": "var(--text-muted)", "font-style": "italic", "font-size": "var(--text-xs)" } }, "Baseline")
      );
    }

    tbody.appendChild(h("tr", null, versionCol, dateCol, scoreCol, actionCol));
  });

  table.appendChild(tbody);
  timelineCont.appendChild(table);
  container.appendChild(timelineCont);
}
