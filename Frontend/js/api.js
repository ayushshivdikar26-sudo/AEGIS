/**
 * AEGIS Standard API Client (api.js)
 * Implements fetch with AbortController, timeouts, error typing, and event dispatching (Part 1 s9).
 */

export class ApiError extends Error {
  constructor(message, { code = "unknown_error", status = 0, requestId = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

const inFlightControllers = new Map();

export function abortSectionRequest(sectionKey) {
  if (inFlightControllers.has(sectionKey)) {
    inFlightControllers.get(sectionKey).abort();
    inFlightControllers.delete(sectionKey);
  }
}

export async function request(path, { method = "GET", body = null, section = null, timeout = 10000 } = {}) {
  if (section) {
    abortSectionRequest(section);
  }

  // Forward dev test control query parameters (e.g., ?fail=permissions, ?delay=500)
  if (typeof window !== "undefined" && window.location) {
    const searchParams = new URLSearchParams(window.location.search);
    let failVal = searchParams.get("fail");
    let delayVal = searchParams.get("delay");

    if (!failVal && window.location.hash.includes("?")) {
      const hashQuery = window.location.hash.split("?")[1];
      const hashParams = new URLSearchParams(hashQuery);
      failVal = hashParams.get("fail");
      delayVal = hashParams.get("delay");
    }

    if (failVal || delayVal) {
      const sep = path.includes("?") ? "&" : "?";
      const extra = new URLSearchParams();
      if (failVal) extra.set("fail", failVal);
      if (delayVal) extra.set("delay", delayVal);
      path = `${path}${sep}${extra.toString()}`;
    }
  }

  const controller = new AbortController();
  if (section) {
    inFlightControllers.set(section, controller);
  }

  const timer = setTimeout(() => {
    controller.abort();
  }, timeout);

  try {
    const headers = {
      Accept: "application/json",
    };
    if (body && typeof body === "object") {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
      credentials: "same-origin",
      signal: controller.signal,
    });

    clearTimeout(timer);

    const requestId = response.headers.get("X-Request-ID");

    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("aegis:unauthorized", { detail: { requestId } }));
      throw new ApiError("Authentication required.", { code: "unauthorized", status: 401, requestId });
    }

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      const errPayload = data && data.error ? data.error : {};
      throw new ApiError(errPayload.message || `Request failed with status ${response.status}`, {
        code: errPayload.code || `http_${response.status}`,
        status: response.status,
        requestId: errPayload.request_id || requestId,
      });
    }

    return data;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new ApiError("Request timed out or was superseded.", { code: "aborted", status: 0 });
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || "Network error occurred.", { code: "network_error", status: 0 });
  } finally {
    if (section && inFlightControllers.get(section) === controller) {
      inFlightControllers.delete(section);
    }
  }
}

// Contract v1 API Methods
export async function getExtensions() {
  return request("/api/extensions");
}

export async function getExtension(id) {
  const encId = encodeURIComponent(id);
  return request(`/api/extensions/${encId}`, { section: "identity" });
}

export async function getPermissions(id) {
  const encId = encodeURIComponent(id);
  return request(`/api/extensions/${encId}/permissions`, { section: "permissions" });
}

export async function getVersions(id) {
  const encId = encodeURIComponent(id);
  return request(`/api/extensions/${encId}/versions`, { section: "versions" });
}

export async function getComparison(id, fromVersion, toVersion) {
  const encId = encodeURIComponent(id);
  const encFrom = encodeURIComponent(fromVersion);
  const encTo = encodeURIComponent(toVersion);
  return request(`/api/extensions/${encId}/compare?from=${encFrom}&to=${encTo}`, { section: "compare" });
}

export async function getCreep(id) {
  const encId = encodeURIComponent(id);
  return request(`/api/extensions/${encId}/creep`, { section: "creep" });
}
