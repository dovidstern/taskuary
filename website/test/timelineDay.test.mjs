import test from "node:test";
import assert from "node:assert/strict";
import { timelineDayLabel } from "../src/timelineDay.js";

test("an empty filter transition never becomes an Invalid Date heading", () => {
  assert.equal(timelineDayLabel(""), "");
  assert.equal(timelineDayLabel("Invalid Date"), "undated");
  assert.equal(timelineDayLabel("not-a-date"), "undated");
});

test("valid days keep their relative timeline label", () => {
  const now = new Date("2026-08-30T12:00:00");
  assert.match(timelineDayLabel("2026-08-30", now), /^Today · /);
  assert.match(timelineDayLabel("2026-08-29", now), /^Yesterday · /);
});
