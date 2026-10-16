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
} from "./api.js";
import { renderSidebarList } from "./render/sidebar.js";
import { renderIdentity } from "./render/identity.js";
import { renderGauge } from "./render/gauge.js";
import { renderAbout } from "./render/about.js";
import { renderPermissions } from "./render/permissions.js";
import { renderVersions } from "./render/versions.js";
import { renderCreep } from "./render/creep.js";
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

// Select and load an extension
async function selectExtension(id) {
  if (!id || !ID_REGEX.test(id)) {
    return;
  }

  window.location.hash = `#/ext/${id}`;
  store.setState({ selectedId: id });

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

    // Render Panels in exact PRD order:
    // Identity, Risk gauge, About, Permissions, Version comparison, Permission creep
    contentCol.replaceChildren();

    contentCol.appendChild(renderIdentity(extData));
    contentCol.appendChild(renderGauge(extData.assessment));
    contentCol.appendChild(renderAbout(extData));

    if (permsData.error) {
      contentCol.appendChild(renderError("Failed to load permissions.", () => selectExtension(id)));
    } else {
      contentCol.appendChild(renderPermissions(permsData));
    }

    contentCol.appendChild(
      renderVersions(versionsData, compData, {
        onVersionChange: async (olderVer, newerVer) => {
          try {
            const updatedComp = await getComparison(id, olderVer, newerVer);
            store.setState({ comparison: updatedComp });
            // Re-render versions panel
            const compSec = document.getElementById("comparison-section");
            if (compSec) {
              const freshPanel = renderVersions(versionsData, updatedComp, {
                onVersionChange: this,
              });
              compSec.replaceWith(freshPanel);
            }
          } catch (err) {
            alert(`Failed to compare versions: ${err.message}`);
          }
        },
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
  // 1. Initialize Animated Threads Canvas
  initThreads("threads");

  // 2. Setup Mobile Navigation
  setupMobileDrawer();

  // 3. Setup Search Bar
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");
  const countEl = document.getElementById("search-count");

  function updateSearch() {
    const q = searchInput.value;
    store.setState({ searchQuery: q });
    if (clearBtn) {
      clearBtn.classList.toggle("is-hidden", !q);
    }
    const state = store.getState();
    const filtered = state.extensions.filter(
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
      searchInput.value = "";
      updateSearch();
      searchInput.focus();
    });
  }

  // 4. Fetch Extensions List
  const listContainer = document.getElementById("extension-list");
  try {
    const data = await getExtensions();
    const exts = data.extensions || [];
    store.setState({ extensions: exts, source: data.source });

    const notice = document.getElementById("fixture-notice");
    if (notice) {
      if (data.source === "fixture") {
        notice.textContent = "Sample data from dev mock API";
        notice.classList.remove("is-hidden");
      } else {
        notice.textContent = `${exts.length} installed extensions monitored`;
        notice.classList.remove("is-hidden");
      }
    }

    renderSidebarList(listContainer, store.getState(), { onSelect: selectExtension });

    // 5. Handle Initial Route
    const hash = window.location.hash;
    const match = hash.match(/^#\/ext\/([A-Za-z0-9._:-]{1,128})$/);
    if (match) {
      selectExtension(match[1]);
    } else if (exts.length > 0) {
      selectExtension(exts[0].id);
    }
  } catch (err) {
    if (listContainer) {
      listContainer.replaceChildren(
        renderError(`Failed to load extensions: ${err.message}`, () => init())
      );
    }
  }

  // Listen for hash changes
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash;
    const match = hash.match(/^#\/ext\/([A-Za-z0-9._:-]{1,128})$/);
    if (match && match[1] !== store.getState().selectedId) {
      selectExtension(match[1]);
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
