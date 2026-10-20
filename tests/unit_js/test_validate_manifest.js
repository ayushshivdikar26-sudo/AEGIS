import test from "node:test";
import assert from "node:assert/strict";
import { validateManifestPreflight } from "../../Frontend/js/lib/validate_manifest.js";

test("validateManifestPreflight accepts valid manifest v3", () => {
  const jsonStr = JSON.stringify({
    manifest_version: 3,
    name: "Valid Extension",
    version: "1.0.0",
    permissions: ["storage"],
  });
  const res = validateManifestPreflight(jsonStr);
  assert.equal(res.valid, true);
  assert.equal(res.effectiveName, "Valid Extension");
});

test("validateManifestPreflight accepts valid manifest v2", () => {
  const jsonStr = JSON.stringify({
    manifest_version: 2,
    name: "Legacy V2 Extension",
    version: "2.1.0",
  });
  const res = validateManifestPreflight(jsonStr);
  assert.equal(res.valid, true);
});

test("validateManifestPreflight rejects malformed JSON", () => {
  const res = validateManifestPreflight("{not valid json}");
  assert.equal(res.valid, false);
  assert.match(res.error, /Malformed JSON syntax/);
});

test("validateManifestPreflight rejects non-object root (array)", () => {
  const res = validateManifestPreflight("[1, 2, 3]");
  assert.equal(res.valid, false);
  assert.match(res.error, /must be a valid JSON object/);
});

test("validateManifestPreflight rejects invalid manifest_version", () => {
  const res = validateManifestPreflight(JSON.stringify({
    manifest_version: 1,
    name: "Bad MV",
    version: "1.0",
  }));
  assert.equal(res.valid, false);
  assert.match(res.error, /manifest_version/);
});

test("validateManifestPreflight rejects missing version", () => {
  const res = validateManifestPreflight(JSON.stringify({
    manifest_version: 3,
    name: "No Version",
  }));
  assert.equal(res.valid, false);
  assert.match(res.error, /missing a valid 'version'/);
});

test("validateManifestPreflight permits missing name if displayName is provided", () => {
  const res = validateManifestPreflight(
    JSON.stringify({ manifest_version: 3, version: "1.0.0" }),
    "Provided Override Name"
  );
  assert.equal(res.valid, true);
  assert.equal(res.effectiveName, "Provided Override Name");
});

test("validateManifestPreflight rejects empty text", () => {
  const res = validateManifestPreflight("");
  assert.equal(res.valid, false);
  assert.match(res.error, /Manifest content is empty/);
});
