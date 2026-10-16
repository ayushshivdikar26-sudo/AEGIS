/**
 * AEGIS About Section Renderer (render/about.js)
 * Displays extension description and its provenance (Part 1 s7.3).
 */

import { h } from "../dom.js";

export function renderAbout(extensionData) {
  const panel = h("section", {
    id: "about-section",
    className: "panel",
    "aria-labelledby": "about-heading",
  });

  panel.appendChild(
    h("div", { className: "section-label", id: "about-heading" }, "About")
  );

  const descObj = extensionData.description || {};
  const text = descObj.text || "";
  const origin = descObj.origin || "unavailable";

  if (text) {
    panel.appendChild(h("p", { dir: "auto" }, text));
    const originLabel = origin === "manifest" ? "From the manifest" : "From extension listing";
    panel.appendChild(
      h(
        "div",
        {
          style: {
            "font-size": "var(--text-xs)",
            "color": "var(--text-muted)",
          },
        },
        originLabel
      )
    );
  } else {
    panel.appendChild(
      h(
        "p",
        {
          style: {
            "color": "var(--text-muted)",
            "font-style": "italic",
          },
        },
        "No description available."
      )
    );
  }

  return panel;
}
