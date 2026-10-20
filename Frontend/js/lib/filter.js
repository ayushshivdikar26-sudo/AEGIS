/**
 * AEGIS Extension Search Filter (Frontend/js/lib/filter.js)
 * Filters extension list by name or browser case-insensitively.
 */

export function filterExtensions(extensions, query) {
  if (!Array.isArray(extensions)) {
    return [];
  }
  if (!query || typeof query !== "string" || !query.trim()) {
    return extensions;
  }
  const q = query.trim().toLowerCase();
  return extensions.filter((ext) => {
    if (!ext) return false;
    const nameMatch = ext.name && ext.name.toLowerCase().includes(q);
    const browserMatch = ext.browser && ext.browser.toLowerCase().includes(q);
    return Boolean(nameMatch || browserMatch);
  });
}
