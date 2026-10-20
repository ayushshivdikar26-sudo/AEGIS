/**
 * AEGIS Identity Section Renderer (render/identity.js)
 * Displays extension logo (120px), name (36px), browser/version mono chip,
 * origin pill (SAMPLE/IMPORTED), inset box "Description of the extension",
 * and quick metadata row (author, permissions count, updated date, store link) (Milestone 2 - Part C2).
 */

import { h } from "../dom.js";

export function renderIdentity(extensionData) {
  const card = h("section", {
    id: "identity-section",
    className: "panel identity-card",
    "aria-labelledby": "identity-heading",
  });

  const ext = extensionData || {};
  const isSample = ext.id && ext.id.startsWith("sample-");

  // 120px logo with 16px radius
  let logoElement;
  if (
    ext.icon_url &&
    (ext.icon_url.startsWith("https:") ||
      ext.icon_url.startsWith("/") ||
      ext.icon_url.startsWith("assets/") ||
      ext.icon_url.startsWith("data:"))
  ) {
    const img = h("img", {
      src: ext.icon_url,
      alt: "",
      className: "identity-logo-img",
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

  // Header Details (Name 36px, Origin pill, Browser/Version chip)
  const titleRow = h(
    "div",
    { className: "identity-title-row" },
    h("h1", { id: "identity-heading", className: "identity-name", dir: "auto" }, ext.name || "Unnamed Extension"),
    h(
      "span",
      { className: isSample ? "chip chip-sample" : "chip chip-imported" },
      isSample ? "SAMPLE" : "IMPORTED"
    )
  );

  const browserName = ext.browser ? ext.browser.toUpperCase() : "CHROME";
  const versionStr = ext.version ? `v${ext.version}` : "v1.0.0";
  const metaRow = h("div", { className: "identity-meta mono" }, `${browserName} • ${versionStr}`);

  const headerDetails = h("div", { className: "identity-details" }, titleRow, metaRow);
  const header = h("div", { className: "identity-header" }, logoElement, headerDetails);
  card.appendChild(header);

  // Inset box: "Description of the extension"
  const descObj = ext.description || {};
  const descText = typeof descObj === "string" ? descObj : descObj.text || ext.catalog_description || "";
  const descBox = h("div", { className: "identity-desc-box" });
  descBox.appendChild(
    h("div", { className: "desc-box-title" }, "Description of the extension")
  );

  if (descText) {
    descBox.appendChild(h("p", { className: "desc-box-text", dir: "auto" }, descText));
    descBox.appendChild(h("div", { className: "desc-box-caption" }, "From the manifest"));
  } else {
    descBox.appendChild(
      h("p", { className: "desc-box-text desc-box-empty" }, "No description available.")
    );
  }
  card.appendChild(descBox);

  // Quick metadata row below: author, permissions count, updated date, and store link (C2)
  const quickMeta = h("div", { className: "identity-quick-meta" });

  const author = ext.author || ext.developer;
  if (author) {
    quickMeta.appendChild(
      h("div", { className: "quick-meta-item" },
        h("span", { className: "quick-meta-label" }, "Author: "),
        h("span", { className: "quick-meta-val" }, author)
      )
    );
  }

  const permsCount = ext.permissions_count !== undefined
    ? ext.permissions_count
    : (ext.assessment && ext.assessment.breakdown ? ext.assessment.breakdown.length : null);
  if (permsCount !== null) {
    quickMeta.appendChild(
      h("div", { className: "quick-meta-item" },
        h("span", { className: "quick-meta-label" }, "Permissions: "),
        h("span", { className: "quick-meta-val" }, `${permsCount} declared`)
      )
    );
  }

  const dateVal = ext.updated_at || ext.updated || ext.last_updated;
  if (dateVal) {
    const d = new Date(dateVal);
    const dateFormatted = !isNaN(d.getTime()) ? d.toLocaleDateString() : String(dateVal).slice(0, 10);
    quickMeta.appendChild(
      h("div", { className: "quick-meta-item" },
        h("span", { className: "quick-meta-label" }, "Updated: "),
        h("span", { className: "quick-meta-val" }, dateFormatted)
      )
    );
  }

  const storeUrl = ext.store_url || (ext.store_id ? `https://chromewebstore.google.com/detail/${ext.store_id}` : null);
  if (storeUrl) {
    const storeLink = h(
      "a",
      {
        href: storeUrl,
        target: "_blank",
        rel: "noopener noreferrer",
        className: "quick-meta-store-link",
      },
      "Web Store",
      // Inline external-link SVG icon
      h("span", {
        className: "external-icon",
        innerHTML: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>`,
      })
    );
    quickMeta.appendChild(storeLink);
  }

  card.appendChild(quickMeta);

  return card;
}
