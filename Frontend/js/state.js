/**
 * AEGIS State Store (state.js)
 * Manages reactive UI state and section-level status tracking.
 */

class Store {
  constructor() {
    this.state = {
      source: "live", // "live" | "fixture"
      extensions: [],
      filteredExtensions: [],
      searchQuery: "",
      selectedId: null,
      selectedExtension: null,
      permissions: null,
      versions: [],
      selectedOlderVersion: null,
      selectedNewerVersion: null,
      comparison: null,
      creep: null,
      sectionStatus: {
        list: "idle", // "idle" | "loading" | "error" | "ready"
        identity: "idle",
        gauge: "idle",
        permissions: "idle",
        versions: "idle",
        creep: "idle",
      },
      sectionErrors: {},
    };
    this.subscribers = new Set();
  }

  getState() {
    return this.state;
  }

  setState(updates) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  setSectionStatus(section, status, error = null) {
    this.state.sectionStatus = {
      ...this.state.sectionStatus,
      [section]: status,
    };
    if (error) {
      this.state.sectionErrors = {
        ...this.state.sectionErrors,
        [section]: error,
      };
    } else {
      const copy = { ...this.state.sectionErrors };
      delete copy[section];
      this.state.sectionErrors = copy;
    }
    this.notify();
  }

  subscribe(listener) {
    this.subscribers.add(listener);
    return () => this.subscribers.delete(listener);
  }

  notify() {
    for (const sub of this.subscribers) {
      try {
        sub(this.state);
      } catch (err) {
        // Silently prevent subscriber errors from cascading
      }
    }
  }
}

export const store = new Store();
