/**
 * AEGIS Non-Technical Guided Demo Helper (render/guide.js)
 * Provides a plain-language introductory banner and quick-select buttons for audience demonstration.
 */

import { h } from "../dom.js";

export function renderGuide({ selectedId, onSelect, onOpenImport }) {
  const guide = h("div", { className: "panel guided-demo-panel" });

  const titleRow = h(
    "div",
    { className: "guided-header" },
    h("span", { className: "guided-tag" }, "Guided Demonstration"),
    h("h2", { className: "guided-title" }, "Browser Extension Permission Auditor"),
    h(
      "p",
      { className: "guided-subtitle" },
      "See what your browser extensions are permitted to do, and detect when updates expand their access to your personal data or browsing history."
    )
  );

  // Quick scenario buttons
  const scenariosBox = h("div", { className: "guided-scenarios-box" });
  scenariosBox.appendChild(
    h("span", { className: "guided-scenarios-label" }, "Interactive Demo Scenarios:")
  );

  const buttonsRow = h("div", { className: "guided-buttons-row" });

  // Scenario 1: Notes Sync (Permission Creep)
  const isNotes = selectedId === "sample-notes-sync";
  const notesBtn = h(
    "button",
    {
      type: "button",
      className: `btn ${isNotes ? "btn-primary" : "btn-secondary"} guided-pill`,
      title: "Shows an extension moving from low risk to high risk across releases",
    },
    "🌟 Sample Notes Sync (Permission Expansion 20 -> 70)"
  );
  notesBtn.addEventListener("click", () => onSelect("sample-notes-sync"));
  buttonsRow.appendChild(notesBtn);

  // Scenario 2: Ad Shield
  const isAd = selectedId === "sample-ad-shield";
  const adBtn = h(
    "button",
    {
      type: "button",
      className: `btn ${isAd ? "btn-primary" : "btn-secondary"} guided-pill`,
      title: "Shows version comparison on an ad-blocking extension",
    },
    "🛡️ Sample Ad Shield (Filter Rules)"
  );
  adBtn.addEventListener("click", () => onSelect("sample-ad-shield"));
  buttonsRow.appendChild(adBtn);

  // Action: Custom Import
  const importBtn = h(
    "button",
    {
      type: "button",
      className: "btn btn-secondary guided-pill",
      title: "Upload or paste your own WebExtension manifest file",
    },
    "+ Import Custom Manifest"
  );
  importBtn.addEventListener("click", onOpenImport);
  buttonsRow.appendChild(importBtn);

  scenariosBox.appendChild(buttonsRow);
  guide.appendChild(titleRow);
  guide.appendChild(scenariosBox);

  return guide;
}
