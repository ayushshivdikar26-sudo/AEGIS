/**
 * AEGIS Secure DOM Builder (dom.js)
 * Enforces textContent-only rendering and rejects inline handlers and style strings (PRD s7.2).
 */

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);

  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined) {
        continue;
      }

      // Security rule: refuse attributes starting with 'on' (no inline event handlers)
      if (key.toLowerCase().startsWith("on")) {
        throw new Error(`Security Violation: Disallowed inline event handler '${key}'`);
      }

      // Security rule: refuse raw string style attributes (use style properties or classes)
      if (key === "style" && typeof value === "string") {
        throw new Error("Security Violation: Raw style strings are disallowed. Use setProperty or classes.");
      }

      if (key === "style" && typeof value === "object") {
        for (const [prop, propVal] of Object.entries(value)) {
          el.style.setProperty(prop, propVal);
        }
      } else if (key === "className") {
        el.className = value;
      } else if (key === "dataset" && typeof value === "object") {
        for (const [dataKey, dataVal] of Object.entries(value)) {
          el.dataset[dataKey] = dataVal;
        }
      } else if (typeof value === "boolean") {
        if (value) {
          el.setAttribute(key, "");
        }
      } else {
        el.setAttribute(key, String(value));
      }
    }
  }

  for (const child of children) {
    if (child === null || child === undefined || child === false) {
      continue;
    }
    if (child instanceof Node) {
      el.appendChild(child);
    } else if (Array.isArray(child)) {
      for (const nested of child) {
        if (nested instanceof Node) {
          el.appendChild(nested);
        } else if (nested !== null && nested !== undefined && nested !== false) {
          el.appendChild(document.createTextNode(String(nested)));
        }
      }
    } else {
      el.appendChild(document.createTextNode(String(child)));
    }
  }

  return el;
}
