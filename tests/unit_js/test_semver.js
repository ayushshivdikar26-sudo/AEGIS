import test from "node:test";
import assert from "node:assert/strict";
import { compareSemver } from "../../Frontend/js/render/versions.js";

test("compareSemver orders numeric semantic versions accurately", () => {
  assert.equal(compareSemver("3.2.58", "3.2.57") > 0, true);
  assert.equal(compareSemver("3.2.57", "3.2.58") < 0, true);
  assert.equal(compareSemver("3.2.57", "3.2.57"), 0);

  // Patch vs minor vs major
  assert.equal(compareSemver("3.10.0", "3.2.58") > 0, true);
  assert.equal(compareSemver("4.0.0", "3.99.99") > 0, true);
  assert.equal(compareSemver("1.0.0.1", "1.0.0") > 0, true);
});

test("compareSemver correctly sorts an array of versions newest first", () => {
  const versions = [
    { version: "1.0.0" },
    { version: "3.2.58" },
    { version: "2.10.1" },
    { version: "3.2.57" },
    { version: "3.10.0" },
  ];

  const sorted = [...versions].sort((a, b) => compareSemver(b.version, a.version));
  const order = sorted.map((v) => v.version);
  assert.deepEqual(order, ["3.10.0", "3.2.58", "3.2.57", "2.10.1", "1.0.0"]);
});
