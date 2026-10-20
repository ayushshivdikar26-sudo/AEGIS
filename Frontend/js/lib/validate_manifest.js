/**
 * Client-Side Pre-Flight WebExtension Manifest Validator (validate_manifest.js)
 * Validates manifest size, JSON syntax, required fields, and versioning before upload.
 */

export function validateManifestPreflight(rawText, displayName = "") {
  if (!rawText || typeof rawText !== "string" || !rawText.trim()) {
    return { valid: false, error: "Manifest content is empty." };
  }

  if (rawText.length > 1048576) {
    return { valid: false, error: "Manifest file exceeds 1 MB limit." };
  }

  let parsed;
  try {
    parsed = JSON.parse(rawText);
  } catch (err) {
    return { valid: false, error: `Malformed JSON syntax: ${err.message}` };
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { valid: false, error: "Manifest JSON must be a valid JSON object." };
  }

  if (!parsed.manifest_version || (parsed.manifest_version !== 2 && parsed.manifest_version !== 3)) {
    return { valid: false, error: "Manifest must specify 'manifest_version' 2 or 3." };
  }

  if (!parsed.version || typeof parsed.version !== "string" || !parsed.version.trim()) {
    return { valid: false, error: "Manifest is missing a valid 'version' string." };
  }

  const effectiveName = (displayName && displayName.trim()) || (parsed.name && String(parsed.name).trim());
  if (!effectiveName) {
    return { valid: false, error: "Manifest is missing a 'name' field. Please provide a Display Name." };
  }

  return { valid: true, manifest: parsed, effectiveName };
}
