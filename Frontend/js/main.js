/**
 * AEGIS Frontend Main Entry Point (main.js)
 * Bootstraps application, hash routing, background threads, and UI event binding.
 */

import { initThreads } from "./threads.js";
import { store } from "./state.js";
import {
  getExtensions,
  getExtension,
  getPermissions,
  getVersions,
  getComparison,
  getCreep,
  importExtension,
  exportHistory,
  importHistory,
  getAIOverview,
} from "./api.js";
import { validateManifestPreflight } from "./lib/validate_manifest.js";
import { renderSidebarList } from "./render/sidebar.js";
import { renderIdentity } from "./render/identity.js";
import { renderGauge } from "./render/gauge.js";
import { renderGuide } from "./render/guide.js";
import { renderAbout } from "./render/about.js";
import { renderPermissions } from "./render/permissions.js";
import { renderVersions } from "./render/versions.js";
import { renderCreep } from "./render/creep.js";
import { renderAIOverview, renderAISkeleton, renderAIError } from "./render/ai_overview.js";
import { renderError, renderLoading } from "./render/states.js";

const ID_REGEX = /^[A-Za-z0-9._:-]{1,128}$/;

// Announce text to polite live region
function announce(message) {
  const el = document.getElementById("status-announcer");
  if (el) {
    el.textContent = message;
  }
}

// Mobile drawer controls
function setupMobileDrawer() {
  const menuBtn = document.getElementById("mobile-menu-btn");
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("drawer-backdrop");

  if (!menuBtn || !sidebar || !backdrop) return;

  function openDrawer() {
    sidebar.classList.add("open");
    backdrop.classList.add("active");
    menuBtn.setAttribute("aria-expanded", "true");
  }

  function closeDrawer() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("active");
    menuBtn.setAttribute("aria-expanded", "false");
    menuBtn.focus();
  }

  menuBtn.addEventListener("click", () => {
    const isOpen = sidebar.classList.contains("open");
    if (isOpen) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  backdrop.addEventListener("click", closeDrawer);

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && sidebar.classList.contains("open")) {
      closeDrawer();
    }
  });
}

// Manifest Import Modal & Workflow
function setupImportModal() {
  const importBtn = document.getElementById("import-btn");
  const backdrop = document.getElementById("import-modal-backdrop");
  const closeBtn = document.getElementById("import-modal-close");
  const cancelBtn = document.getElementById("import-cancel-btn");
  const form = document.getElementById("import-form");
  const fileInput = document.getElementById("import-file");
  const pasteInput = document.getElementById("import-json-paste");
  const browserInput = document.getElementById("import-browser");
  const storeIdInput = document.getElementById("import-store-id");
  const displayNameInput = document.getElementById("import-display-name");
  const errorBanner = document.getElementById("import-error-banner");
  const submitBtn = document.getElementById("import-submit-btn");
  const submitText = document.getElementById("import-submit-text");

  if (!importBtn || !backdrop || !form) return;

  function openModal() {
    backdrop.classList.add("active");
    backdrop.setAttribute("aria-hidden", "false");
    importBtn.setAttribute("aria-expanded", "true");
    if (errorBanner) errorBanner.classList.add("is-hidden");
    if (fileInput) fileInput.focus();
  }

  function closeModal() {
    backdrop.classList.remove("active");
    backdrop.setAttribute("aria-hidden", "true");
    importBtn.setAttribute("aria-expanded", "false");
    form.reset();
    if (errorBanner) errorBanner.classList.add("is-hidden");
    if (submitBtn) submitBtn.disabled = false;
    if (submitText) submitText.textContent = "Analyze Manifest";
    importBtn.focus();
  }

  importBtn.addEventListener("click", openModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeModal();
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && backdrop.classList.contains("active")) {
      closeModal();
    }
  });

  function showError(msg) {
    if (errorBanner) {
      errorBanner.textContent = msg;
      errorBanner.classList.remove("is-hidden");
    }
    announce(`Import error: ${msg}`);
  }

  function setSubmitting(isSubmitting) {
    if (submitBtn) submitBtn.disabled = isSubmitting;
    if (submitText) submitText.textContent = isSubmitting ? "Analyzing Manifest..." : "Analyze Manifest";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (errorBanner) errorBanner.classList.add("is-hidden");

    let manifestRaw = "";
    let fileName = "manifest.json";

    const file = fileInput.files && fileInput.files[0];
    const pasted = pasteInput.value.trim();

    if (file) {
      if (!file.name.toLowerCase().endsWith(".json") && file.type && !file.type.includes("json")) {
        showError("Only .json manifest files are supported.");
        return;
      }
      if (file.size > 1048576) {
        showError("Manifest file exceeds 1 MB limit.");
        return;
      }
      try {
        manifestRaw = await file.text();
        fileName = file.name;
      } catch (err) {
        showError(`Could not read file: ${err.message}`);
        return;
      }
    } else if (pasted) {
      manifestRaw = pasted;
    } else {
      showError("Please select a manifest file or paste manifest JSON.");
      return;
    }

    // Pre-flight client JSON syntax and structure validation
    const validation = validateManifestPreflight(manifestRaw, displayNameInput ? displayNameInput.value : "");
    if (!validation.valid) {
      showError(validation.error);
      return;
    }

    // Prepare FormData
    const formData = new FormData();
    const manifestBlob = new Blob([manifestRaw], { type: "application/json" });
    formData.append("manifest", manifestBlob, fileName);
    formData.append("browser", (browserInput && browserInput.value) || "chrome");

    const storeIdVal = storeIdInput.value.trim();
    if (storeIdVal) {
      formData.append("store_id", storeIdVal);
    }

    const displayNameVal = displayNameInput.value.trim();
    if (displayNameVal) {
      formData.append("display_name", displayNameVal);
    }

    setSubmitting(true);

    try {
      const result = await importExtension(formData);
      closeModal();
      announce(`Extension ${result.extension.name} imported successfully.`);

      // Refresh extension list
      const listContainer = document.getElementById("extension-list");
      const listData = await getExtensions();
      const exts = listData.extensions || [];
      store.setState({ extensions: exts, source: listData.source });

      const notice = document.getElementById("fixture-notice");
      if (notice) {
        notice.textContent = `${exts.length} extensions in catalogue`;
        notice.classList.remove("is-hidden");
      }

      if (listContainer) {
        renderSidebarList(listContainer, store.getState(), { onSelect: selectExtension });
      }

      // Automatically select the newly imported extension
      if (result.extension && result.extension.id) {
        selectExtension(result.extension.id);
      }
    } catch (err) {
      setSubmitting(false);
      showError(err.message || "Failed to import extension manifest.");
    }
  });
}

// Select and load an extension
async function selectExtension(id) {
  if (!id || !ID_REGEX.test(id)) {
    return;
  }

  window.location.hash = `#/ext/${id}`;
  try {
    localStorage.setItem("aegis_selected_extension", id);
  } catch {}
  store.setState({ selectedId: id });

  // Update selection highlight on all sidebar rows immediately in DOM
  const listContainer = document.getElementById("extension-list");
  if (listContainer) {
    const rows = listContainer.querySelectorAll(".ext-row");
    rows.forEach((row) => {
      const match = row.dataset.id === id;
      row.classList.toggle("is-selected", match);
      row.setAttribute("aria-current", match ? "true" : "false");
      row.setAttribute("aria-selected", match ? "true" : "false");
      row.setAttribute("tabindex", match ? "0" : "-1");
      if (match) {
        row.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  // Close mobile drawer on selection if open
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("drawer-backdrop");
  if (sidebar && sidebar.classList.contains("open")) {
    sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
  }

  const contentCol = document.getElementById("content-column");
  if (!contentCol) return;

  contentCol.replaceChildren(renderLoading("Loading extension data..."));

  try {
    // 1. Fetch extension metadata & assessment
    const extData = await getExtension(id);
    store.setState({ selectedExtension: extData });

    // Update mobile title
    const mobTitle = document.getElementById("mobile-header-title");
    if (mobTitle) {
      mobTitle.textContent = extData.name || "AEGIS";
    }

    // 2. Fetch permissions, versions, and creep in parallel
    const [permsData, versionsData, creepData] = await Promise.all([
      getPermissions(id).catch((err) => {
        return { error: err.message };
      }),
      getVersions(id).catch((err) => {
        return { error: err.message, versions: [] };
      }),
      getCreep(id).catch((err) => {
        return { error: err.message, available: false };
      }),
    ]);

    store.setState({
      permissions: permsData,
      versions: versionsData.versions || [],
      creep: creepData,
    });

    // 3. Fetch comparison if >= 2 versions exist
    let compData = null;
    const vList = versionsData.versions || [];
    if (vList.length >= 2) {
      try {
        compData = await getComparison(id, vList[1].version, vList[0].version);
      } catch {
        compData = null;
      }
    }
    store.setState({ comparison: compData });

    // Render Panels:
    contentCol.replaceChildren();

    // Guided Demo Quick-Selector Banner (For Non-Technical Audiences)
    contentCol.appendChild(
      renderGuide({
        selectedId: id,
        onSelect: selectExtension,
        onOpenImport: () => {
          const btn = document.getElementById("import-btn");
          if (btn) btn.click();
        },
      })
    );

    contentCol.appendChild(renderIdentity(extData));
    contentCol.appendChild(renderGauge(extData.assessment));
    contentCol.appendChild(renderAbout(extData));

    // Milestone 2: AI Overview Card (Non-blocking async load)
    contentCol.appendChild(renderAISkeleton());

    const loadAI = async (forceRefresh = false, olderV = null, newerV = null) => {
      try {
        const aiData = await getAIOverview(id, {
          version: newerV || extData.version,
          olderVersion: olderV || (vList.length >= 2 ? vList[1].version : null),
          forceRefresh,
        });
        const activeCard = renderAIOverview(aiData, {
          onRegenerate: () => {
            const currentSection = document.getElementById("ai-overview-section");
            if (currentSection) {
              currentSection.replaceWith(renderAISkeleton());
            }
            loadAI(true, olderV, newerV);
          },
        });
        const currentSection = document.getElementById("ai-overview-section");
        if (currentSection) {
          currentSection.replaceWith(activeCard);
        }
      } catch (err) {
        console.warn("AI overview error:", err);
        const errCard = renderAIError(
          "AI overview unavailable: " + err.message,
          () => {
            const currentSection = document.getElementById("ai-overview-section");
            if (currentSection) {
              currentSection.replaceWith(renderAISkeleton());
            }
            loadAI(false, olderV, newerV);
          }
        );
        const currentSection = document.getElementById("ai-overview-section");
        if (currentSection) {
          currentSection.replaceWith(errCard);
        }
      }
    };
    loadAI(false);

    if (permsData.error) {
      contentCol.appendChild(renderError("Failed to load permissions.", () => selectExtension(id)));
    } else {
      contentCol.appendChild(renderPermissions(permsData));
    }

    const handleVersionDiff = async (olderVer, newerVer) => {
      try {
        const updatedComp = await getComparison(id, olderVer, newerVer);
        store.setState({ comparison: updatedComp });
        // Re-render versions panel with updated comparison
        const compSec = document.getElementById("comparison-section");
        if (compSec) {
          const freshPanel = renderVersions(versionsData, updatedComp, {
            onVersionChange: handleVersionDiff,
          });
          compSec.replaceWith(freshPanel);
        }
        // Update AI overview with the compared versions
        const currentSection = document.getElementById("ai-overview-section");
        if (currentSection) {
          currentSection.replaceWith(renderAISkeleton());
        }
        loadAI(false, olderVer, newerVer);
      } catch (err) {
        alert(`Failed to compare versions: ${err.message}`);
      }
    };

    contentCol.appendChild(
      renderVersions(versionsData, compData, {
        onVersionChange: handleVersionDiff,
      })
    );

    contentCol.appendChild(renderCreep(creepData));

    // Announce to polite live region
    const scoreVal = extData.assessment ? extData.assessment.risk_score : 0;
    const levelVal = extData.assessment ? extData.assessment.risk_level : "low";
    announce(`Loaded ${extData.name}, permission risk ${scoreVal} of 100, ${levelVal}.`);
  } catch (err) {
    contentCol.replaceChildren(
      renderError(`Failed to load extension: ${err.message}`, () => selectExtension(id))
    );
  }
}

// Bootstrap
async function init() {
  // 1. Initialize Animated Threads Canvas (Fail-safe)
  try {
    initThreads("threads");
  } catch (err) {
    console.warn("initThreads warning:", err);
  }

  // 2. Setup Mobile Navigation (Fail-safe)
  try {
    setupMobileDrawer();
  } catch (err) {
    console.warn("setupMobileDrawer warning:", err);
  }

  // 2b. Setup Manifest Import Modal
  setupImportModal();

  // 3. Setup Search Bar
  try {
    const searchInput = document.getElementById("search-input");
    const clearBtn = document.getElementById("search-clear-btn");
    const countEl = document.getElementById("search-count");

    function updateSearch() {
      const q = searchInput ? searchInput.value : "";
      store.setState({ searchQuery: q });
      if (clearBtn) {
        clearBtn.classList.toggle("is-hidden", !q);
      }
      const state = store.getState();
      const filtered = (state.extensions || []).filter(
        (e) =>
          (e.name && e.name.toLowerCase().includes(q.toLowerCase())) ||
          (e.browser && e.browser.toLowerCase().includes(q.toLowerCase()))
      );
      if (countEl) {
        countEl.textContent = q ? `${filtered.length} extensions found` : "";
      }
      const listContainer = document.getElementById("extension-list");
      if (listContainer) {
        renderSidebarList(listContainer, state, { onSelect: selectExtension });
      }
    }

    if (searchInput) {
      searchInput.addEventListener("input", updateSearch);
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (searchInput) {
          searchInput.value = "";
          searchInput.focus();
        }
        updateSearch();
      });
    }
  } catch (err) {
    console.warn("search setup warning:", err);
  }

  // 4. Setup History Export & Import (Milestone 1c)
  try {
    const exportBtn = document.getElementById("export-history-btn");
    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        try {
          const backupData = await exportHistory();
          const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `aegis-history-backup-${new Date().toISOString().slice(0, 10)}.json`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          announce("Snapshot history exported successfully.");
        } catch (err) {
          alert(`Failed to export history: ${err.message}`);
        }
      });
    }

    const importBtn = document.getElementById("import-history-btn");
    const importFileInput = document.getElementById("import-history-file");
    if (importBtn && importFileInput) {
      importBtn.addEventListener("click", () => {
        importFileInput.click();
      });

      importFileInput.addEventListener("change", async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
          const text = await file.text();
          const jsonPayload = JSON.parse(text);
          const res = await importHistory(jsonPayload);
          announce(`History imported: ${res.imported_snapshots} snapshots loaded.`);
          alert(`Import successful! ${res.imported_snapshots} snapshots imported (${res.skipped_snapshots} existing skipped).`);
          window.location.reload();
        } catch (err) {
          alert(`Import failed: ${err.message}`);
        } finally {
          importFileInput.value = "";
        }
      });
    }
  } catch (err) {
    console.warn("history buttons warning:", err);
  }

  // 5. Listen for hash changes
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash;
    const match = hash.match(/^#\/ext\/([A-Za-z0-9._:-]{1,128})$/);
    if (match && match[1] !== store.getState().selectedId) {
      selectExtension(match[1]);
    }
  });

  // 6. Fetch Extensions List and Initialize Selection
  const listContainer = document.getElementById("extension-list");
  try {
    const data = await getExtensions();
    const exts = (data && data.extensions) || [];
    store.setState({ extensions: exts, source: data ? data.source : "imported" });

    const notice = document.getElementById("fixture-notice");
    if (notice) {
      if (data && data.source === "fixture") {
        notice.textContent = "Sample data from dev mock API";
        notice.classList.remove("is-hidden");
      } else {
        notice.textContent = `${exts.length} installed extensions monitored`;
        notice.classList.remove("is-hidden");
      }
    }

    if (listContainer) {
      renderSidebarList(listContainer, store.getState(), { onSelect: selectExtension });
    }

    // Handle Initial Route & Persistence (Milestone 1a)
    const hash = window.location.hash;
    const match = hash.match(/^#\/ext\/([A-Za-z0-9._:-]{1,128})$/);
    const savedId = (() => {
      try {
        return localStorage.getItem("aegis_selected_extension");
      } catch {
        return null;
      }
    })();

    if (match && exts.some((e) => e.id === match[1])) {
      selectExtension(match[1]);
    } else if (savedId && exts.some((e) => e.id === savedId)) {
      selectExtension(savedId);
    } else if (exts.length > 0) {
      selectExtension(exts[0].id);
    }
  } catch (err) {
    console.error("Failed to load extensions:", err);
    if (listContainer) {
      listContainer.replaceChildren(
        renderError(`Failed to load extensions: ${err.message}`, () => init())
      );
    }
  }
}

// Bootstrap with readyState check to guarantee execution in all browsers
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    init().catch(console.error);
  });
} else {
  init().catch(console.error);
}
