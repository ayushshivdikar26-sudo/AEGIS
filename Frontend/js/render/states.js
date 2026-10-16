/**
 * AEGIS State Components (render/states.js)
 * Standalone rendering for loading, error with retry, and empty states (Part 1 s10).
 */

import { h } from "../dom.js";

export function renderLoading(message = "Loading...") {
  return h(
    "div",
    { className: "state-message" },
    h("span", { className: "state-loading" }, message)
  );
}

export function renderError(message = "An error occurred.", onRetry = null) {
  const container = h(
    "div",
    { className: "state-message" },
    h("p", null, message)
  );

  if (onRetry && typeof onRetry === "function") {
    const retryBtn = h(
      "button",
      { className: "btn btn-secondary", type: "button" },
      "Retry"
    );
    retryBtn.addEventListener("click", () => onRetry());
    container.appendChild(retryBtn);
  }

  return container;
}

export function renderEmpty(title = "Nothing to display", message = "") {
  return h(
    "div",
    { className: "state-message" },
    h("h3", null, title),
    message ? h("p", null, message) : null
  );
}
