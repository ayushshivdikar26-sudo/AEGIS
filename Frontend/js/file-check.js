/**
 * AEGIS Protocol Diagnostic Check (file-check.js)
 * Alerts users if opened via file:// URL where modern browser security blocks ES Modules and fetch().
 */
(function () {
  if (window.location.protocol === "file:") {
    function displayWarning() {
      const listEl = document.getElementById("extension-list");
      if (listEl) {
        listEl.innerHTML =
          '<div style="padding: 16px; color: #f87171; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; font-size: 13px; line-height: 1.6; background: rgba(239, 68, 68, 0.12); border: 1px solid #ef4444; border-radius: 8px; margin: 12px 8px;">' +
          '<strong style="color: #ef4444; font-size: 14px; display: block; margin-bottom: 6px;">Cannot run via file:// protocol</strong>' +
          'Web browsers block ES modules and API requests on local files.<br><br>' +
          '<strong>To view AEGIS:</strong><br>' +
          'Open your browser and navigate to:<br>' +
          '<a href="http://127.0.0.1:8000" style="color: #38bdf8; text-decoration: underline; font-weight: bold; font-size: 14px; display: inline-block; margin-top: 4px;">http://127.0.0.1:8000</a>' +
          '</div>';
      }
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", displayWarning);
    } else {
      displayWarning();
    }
  }
})();
