/**
 * AEGIS AI Security Overview Renderer (render/ai_overview.js)
 * Implements AI Overview card, loading skeleton, fallback handling,
 * creep explanation, action checklist, and disclaimer (Milestone 2 - Part C5).
 * Strictly renders via textContent for XSS safety.
 */

import { h } from "../dom.js";

export function renderAISkeleton() {
  return h(
    "section",
    { id: "ai-overview-section", className: "panel ai-card is-loading", "aria-busy": "true" },
    h(
      "div",
      { className: "ai-header-row" },
      h(
        "div",
        { className: "section-label" },
        h("span", { className: "ai-sparkle-icon", "aria-hidden": "true" }, "✦"),
        " AI Security Overview"
      ),
      h("span", { className: "chip ai-chip-loading" }, "ANALYZING...")
    ),
    h(
      "div",
      { className: "ai-skeleton-container" },
      h("div", { className: "skeleton-line", style: { "--sk-w": "90%", "--sk-h": "14px" } }),
      h("div", { className: "skeleton-line", style: { "--sk-w": "96%", "--sk-h": "14px" } }),
      h("div", { className: "skeleton-line", style: { "--sk-w": "75%", "--sk-h": "14px" } }),
      h("div", { className: "skeleton-line", style: { "--sk-w": "85%", "--sk-h": "14px" } })
    ),
    h(
      "div",
      { className: "ai-disclaimer" },
      "AI-generated from the manifest and description. AEGIS does not inspect extension code."
    )
  );
}

export function renderAIError(errorMessage, onRetry) {
  const panel = h(
    "section",
    { id: "ai-overview-section", className: "panel ai-card ai-error-card" },
    h(
      "div",
      { className: "ai-header-row" },
      h(
        "div",
        { className: "section-label" },
        h("span", { className: "ai-sparkle-icon", "aria-hidden": "true" }, "✦"),
        " AI Security Overview"
      ),
      h("span", { className: "chip chip-high" }, "UNAVAILABLE")
    ),
    h(
      "div",
      { className: "ai-error-body" },
      h("p", { className: "ai-error-text" }, errorMessage || "AI overview is currently unavailable.")
    ),
    h(
      "div",
      { className: "ai-footer-row" },
      onRetry
        ? h(
            "button",
            {
              type: "button",
              className: "btn btn-secondary ai-retry-btn",
            },
            "Retry AI Overview"
          )
        : null,
      h(
        "div",
        { className: "ai-disclaimer-italic" },
        "AEGIS continues to evaluate deterministic permission rules."
      )
    )
  );

  const retryBtn = panel.querySelector(".ai-retry-btn");
  if (retryBtn && onRetry) {
    retryBtn.addEventListener("click", () => onRetry());
  }

  return panel;
}

export function renderAIOverview(data, { onRegenerate } = {}) {
  const panel = h(
    "section",
    { id: "ai-overview-section", className: "panel ai-card", "aria-labelledby": "ai-overview-heading" }
  );

  const isFallback = Boolean(data.is_fallback);

  // 1. Header Row
  const headerRow = h(
    "div",
    { className: "ai-header-row" },
    h(
      "div",
      { className: "section-label", id: "ai-overview-heading" },
      h("span", { className: "ai-sparkle-icon", "aria-hidden": "true" }, "✦"),
      " AI Security Overview"
    ),
    h(
      "div",
      { className: "ai-header-meta" },
      isFallback
        ? h("span", { className: "chip chip-mid" }, "FALLBACK")
        : h("span", { className: "chip chip-ready" }, "READY"),
      data.cached && !isFallback ? h("span", { className: "ai-badge ai-badge-cached" }, "Cached") : null,
      !isFallback ? h("span", { className: "ai-badge" }, data.model || "Groq") : null,
      onRegenerate && !isFallback
        ? h(
            "button",
            {
              type: "button",
              className: "ai-regen-btn",
              title: "Regenerate overview with fresh AI analysis",
              "aria-label": "Regenerate AI overview",
            },
            "↻ Regenerate"
          )
        : null
    )
  );
  panel.appendChild(headerRow);

  // 1b. Fallback Banner if fallback model was used
  if (isFallback) {
    const fallbackBanner = h(
      "div",
      { className: "ai-fallback-banner" },
      h("span", { className: "ai-fallback-text" }, "Generated from rules because the AI service was busy"),
      onRegenerate
        ? h(
            "button",
            {
              type: "button",
              className: "btn btn-secondary ai-retry-btn",
            },
            "Retry AI Overview"
          )
        : null
    );
    panel.appendChild(fallbackBanner);
  }

  // 2. Summary Block
  panel.appendChild(
    h(
      "div",
      { className: "ai-block" },
      h("h4", { className: "ai-subheading" }, "Summary"),
      h("p", { className: "ai-summary-text", dir: "auto" }, data.summary || "No summary provided.")
    )
  );

  // 3. Permission Fit & Sensitivity Block
  panel.appendChild(
    h(
      "div",
      { className: "ai-block" },
      h("h4", { className: "ai-subheading" }, "Permission Consistency & Sensitive Capabilities"),
      h("p", { className: "ai-fit-text", dir: "auto" }, data.permission_fit || "No permission fit analysis available.")
    )
  );

  // 4. Creep Analysis Block
  const creepBlock = h("div", { className: "ai-block ai-creep-section" });
  if (data.creep_detected && Array.isArray(data.creep_risks) && data.creep_risks.length > 0) {
    creepBlock.appendChild(
      h(
        "div",
        { className: "ai-creep-alert" },
        h("span", { className: "chip chip-high" }, "Creep Risks Detected"),
        h(
          "ul",
          { className: "ai-risk-list" },
          data.creep_risks.map((risk) => h("li", { className: "ai-risk-item", dir: "auto" }, risk))
        )
      )
    );
  } else {
    creepBlock.appendChild(
      h(
        "div",
        { className: "ai-no-creep-banner" },
        h("span", { className: "ai-check-icon", "aria-hidden": "true" }, "✓"),
        h("span", null, "No permission creep detected between versions.")
      )
    );
  }
  panel.appendChild(creepBlock);

  // 5. Recommended Actions
  if (Array.isArray(data.recommended_actions) && data.recommended_actions.length > 0) {
    panel.appendChild(
      h(
        "div",
        { className: "ai-block" },
        h("h4", { className: "ai-subheading" }, "Recommended Actions"),
        h(
          "ul",
          { className: "ai-actions-list" },
          data.recommended_actions.map((act) =>
            h(
              "li",
              { className: "ai-action-item" },
              h("span", { className: "ai-action-bullet", "aria-hidden": "true" }, "→"),
              h("span", { className: "ai-action-text", dir: "auto" }, act)
            )
          )
        )
      )
    );
  }

  // 6. Disclaimer Footer
  panel.appendChild(
    h(
      "div",
      { className: "ai-disclaimer" },
      data.disclaimer || "AI-generated from the manifest and description. AEGIS does not inspect extension code."
    )
  );

  // Bind retry / regenerate click
  const retryBtn = panel.querySelector(".ai-retry-btn");
  if (retryBtn && onRegenerate) {
    retryBtn.addEventListener("click", () => onRegenerate());
  }

  const regenBtn = panel.querySelector(".ai-regen-btn");
  if (regenBtn && onRegenerate) {
    regenBtn.addEventListener("click", () => onRegenerate());
  }

  return panel;
}
