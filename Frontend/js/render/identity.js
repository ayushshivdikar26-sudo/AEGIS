/**
 * AEGIS Identity Section Renderer (render/identity.js)
 * Displays extension logo, name, browser version, and metadata (Part 1 s7.1).
 */

import { h } from "../dom.js";

export function renderIdentity(extensionData) {
  const panel = h("section", {
    id: "identity-section",
    className: "panel",
    "aria-labelledby": "identity-heading",
  });

  const ext = extensionData;

  // 96px logo with letter fallback
  let logoElement;
  if (ext.icon_url && (ext.icon_url.startsWith("https:") || ext.icon_url.startsWith("/") || ext.icon_url.startsWith("assets/") || ext.icon_url.startsWith("data:"))) {
    const img = h("img", {
      src: ext.icon_url,
      alt: "",
      referrerpolicy: "no-referrer",
    });
    img.addEventListener("error", () => {
      img.replaceWith(document.createTextNode((ext.name || "E").charAt(0).toUpperCase()));
    });
    logoElement = h("div", { className: "identity-logo" }, img);
  } else {
    const letter = (ext.name || "E").charAt(0).toUpperCase();
    logoElement = h("div", { className: "identity-logo" }, letter);
  }

  // Name and meta
  const metaParts = [];
  if (ext.browser) {
    metaParts.push(ext.browser);
  }
  if (ext.version) {
    metaParts.push(`v${ext.version}`);
  }

  const details = h(
    "div",
    { className: "identity-details" },
    h("h1", { id: "identity-heading", dir: "auto" }, ext.name || "Unnamed Extension"),
    h(
      "div",
      { className: "identity-meta" },
      ext.browser ? `${ext.browser} · ` : "",
      ext.version ? h("span", { className: "mono" }, `v${ext.version}`) : ""
    )
  );

  if (ext.developer) {
    details.appendChild(
      h("div", { className: "identity-meta" }, `Developer: ${ext.developer}`)
    );
  }

  const header = h("div", { className: "identity-header" }, logoElement, details);
  panel.appendChild(header);

  // Honest sample vs imported identification
  const isSample = ext.id && ext.id.startsWith("sample-");
  const callout = h(
    "div",
    {
      className: `identity-callout ${isSample ? "callout-sample" : "callout-imported"}`,
      style: {
        "margin-top": "var(--s-3)",
        "padding": "var(--s-2) var(--s-3)",
        "border-radius": "var(--radius-sm)",
        "font-size": "var(--text-xs)",
        "display": "flex",
        "align-items": "baseline",
        "gap": "var(--s-2)",
      },
    },
    h(
      "span",
      { style: { "font-weight": "700", "white-space": "nowrap" } },
      isSample ? "DEMO SAMPLE:" : "IMPORTED DATA:"
    ),
    h(
      "span",
      null,
      isSample
        ? "This is a demonstration sample with real WebExtension manifest snapshots illustrating cross-version changes."
        : "WebExtension manifest snapshot analyzed by the AEGIS engine."
    )
  );
  panel.appendChild(callout);

  return panel;
}
