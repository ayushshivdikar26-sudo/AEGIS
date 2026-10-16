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
  if (ext.icon_url && (ext.icon_url.startsWith("https:") || ext.icon_url.startsWith("/"))) {
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

  return panel;
}
