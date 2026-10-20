/**
 * AEGIS Sidebar Renderer (render/sidebar.js)
 * Implements extension list, roving tabindex keyboard navigation, search, and risk indicators (Part 1 s7.8).
 */

import { h } from "../dom.js";
import { filterExtensions } from "../lib/filter.js";
import { scoreColor } from "../lib/risk.js";

export function renderSidebarList(container, state, { onSelect }) {
  container.replaceChildren();

  const filtered = filterExtensions(state.extensions, state.searchQuery);

  if (filtered.length === 0) {
    if (state.searchQuery) {
      container.appendChild(
        h("div", { className: "state-message" }, "No extensions match your search.")
      );
    } else {
      container.appendChild(
        h("div", { className: "state-message" }, "No extensions found.")
      );
    }
    return;
  }

  const rowElements = [];

  filtered.forEach((ext, index) => {
    const isSelected = ext.id === state.selectedId;

    // 32px icon with fallback
    let iconElement;
    if (ext.icon_url && (ext.icon_url.startsWith("https:") || ext.icon_url.startsWith("/") || ext.icon_url.startsWith("assets/") || ext.icon_url.startsWith("data:"))) {
      const img = h("img", {
        src: ext.icon_url,
        alt: "",
        referrerpolicy: "no-referrer",
      });
      img.addEventListener("error", () => {
        img.replaceWith(document.createTextNode((ext.name || "E").charAt(0).toUpperCase()));
      });
      iconElement = h("div", { className: "ext-icon-tile" }, img);
    } else {
      const letter = (ext.name || "E").charAt(0).toUpperCase();
      iconElement = h("div", { className: "ext-icon-tile" }, letter);
    }

    // Name, badge & browser
    const isSample = ext.id && ext.id.startsWith("sample-");
    const badgeLabel = isSample ? "Sample" : "Imported";
    const badgeClass = isSample ? "badge-sample" : "badge-imported";

    const info = h(
      "div",
      { className: "ext-info" },
      h("div", { className: "ext-name", dir: "auto" }, ext.name || "Unnamed Extension"),
      h(
        "div",
        { className: "ext-browser-meta" },
        h("span", { className: `ext-badge ${badgeClass}` }, badgeLabel),
        h("span", { className: "ext-browser" }, ext.browser || "Unknown Browser")
      )
    );

    // Risk indicator: word + 40x4px score bar
    const scoreVal = ext.risk_score || 0;
    const riskWord = (ext.risk_level || "low").toUpperCase();
    const barColor = scoreColor(scoreVal);

    const riskBlock = h(
      "div",
      { className: "ext-risk-block" },
      h("span", { className: "ext-risk-word" }, riskWord === "MEDIUM" ? "MED" : riskWord),
      h(
        "div",
        { className: "ext-risk-bar-track" },
        h("div", {
          className: "ext-risk-bar-fill",
          style: {
            "--score-width": `${scoreVal}%`,
            "--score-color": barColor,
          },
        })
      )
    );

    // Row button with roving tabindex
    const row = h(
      "button",
      {
        type: "button",
        role: "listitem",
        className: "ext-row",
        tabIndex: isSelected || (!state.selectedId && index === 0) ? 0 : -1,
        "aria-current": isSelected ? "true" : "false",
        dataset: { id: ext.id, index },
      },
      iconElement,
      info,
      riskBlock
    );

    row.addEventListener("click", () => {
      onSelect(ext.id);
    });

    row.addEventListener("keydown", (e) => {
      let targetIndex = null;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        targetIndex = (index + 1) % rowElements.length;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        targetIndex = (index - 1 + rowElements.length) % rowElements.length;
      } else if (e.key === "Home") {
        e.preventDefault();
        targetIndex = 0;
      } else if (e.key === "End") {
        e.preventDefault();
        targetIndex = rowElements.length - 1;
      }

      if (targetIndex !== null && rowElements[targetIndex]) {
        rowElements.forEach((r) => r.setAttribute("tabindex", "-1"));
        rowElements[targetIndex].setAttribute("tabindex", "0");
        rowElements[targetIndex].focus();
      }
    });

    rowElements.push(row);
    container.appendChild(row);
  });
}
