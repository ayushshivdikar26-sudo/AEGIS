import test from "node:test";
import assert from "node:assert/strict";
import { scoreToLevel, scoreToAngle, pointOnArc, arcPath, scoreColor } from "../../Frontend/js/lib/risk.js";

test("scoreToLevel maps scores correctly across thresholds", () => {
  const thresholds = { low_max: 34, mid_max: 69 };
  assert.equal(scoreToLevel(0, thresholds), "low");
  assert.equal(scoreToLevel(34, thresholds), "low");
  assert.equal(scoreToLevel(35, thresholds), "medium");
  assert.equal(scoreToLevel(69, thresholds), "medium");
  assert.equal(scoreToLevel(70, thresholds), "high");
  assert.equal(scoreToLevel(100, thresholds), "high");
});

test("scoreToAngle computes needle angle across 180 degree semicircle", () => {
  assert.equal(scoreToAngle(0), -90);
  assert.equal(scoreToAngle(50), 0);
  assert.equal(scoreToAngle(100), 90);
  // Clamping test
  assert.equal(scoreToAngle(-10), -90);
  assert.equal(scoreToAngle(120), 90);
});

test("pointOnArc computes coordinates on semicircle", () => {
  const p0 = pointOnArc(120, 120, 100, 0); // Leftmost
  assert.equal(p0.x, 20);
  assert.equal(p0.y, 120);

  const p50 = pointOnArc(120, 120, 100, 50); // Top center
  assert.equal(p50.x, 120);
  assert.equal(p50.y, 20);

  const p100 = pointOnArc(120, 120, 100, 100); // Rightmost
  assert.equal(p100.x, 220);
  assert.equal(p100.y, 120);
});

test("arcPath constructs valid SVG path syntax", () => {
  const path = arcPath(120, 120, 100, 0, 35);
  assert.match(path, /^M 20 120 A 100 100 0 0 1/);
});

test("scoreColor maps to CSS variable names", () => {
  assert.equal(scoreColor(20), "var(--risk-low)");
  assert.equal(scoreColor(50), "var(--risk-mid)");
  assert.equal(scoreColor(80), "var(--risk-high)");
});
