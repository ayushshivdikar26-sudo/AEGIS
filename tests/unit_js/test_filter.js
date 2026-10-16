import test from "node:test";
import assert from "node:assert/strict";
import { filterExtensions } from "../../Frontend/js/lib/filter.js";

const SAMPLE_EXTENSIONS = [
  { id: "1", name: "Sample Notes Sync", browser: "Google Chrome" },
  { id: "2", name: "Sample Tab Manager", browser: "Mozilla Firefox" },
  { id: "3", name: "Ad Shield Pro", browser: "Google Chrome" },
];

test("filterExtensions returns all when query is empty", () => {
  const result = filterExtensions(SAMPLE_EXTENSIONS, "");
  assert.equal(result.length, 3);
});

test("filterExtensions matches extension name case-insensitively", () => {
  const result = filterExtensions(SAMPLE_EXTENSIONS, "notes");
  assert.equal(result.length, 1);
  assert.equal(result[0].name, "Sample Notes Sync");
});

test("filterExtensions matches browser name", () => {
  const result = filterExtensions(SAMPLE_EXTENSIONS, "firefox");
  assert.equal(result.length, 1);
  assert.equal(result[0].name, "Sample Tab Manager");
});

test("filterExtensions returns empty array on no match", () => {
  const result = filterExtensions(SAMPLE_EXTENSIONS, "nonexistent");
  assert.equal(result.length, 0);
});

test("filterExtensions handles null or non-array inputs safely", () => {
  assert.deepEqual(filterExtensions(null, "test"), []);
  assert.deepEqual(filterExtensions(undefined, "test"), []);
});
