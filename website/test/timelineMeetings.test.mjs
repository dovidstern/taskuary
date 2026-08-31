import test from "node:test";
import assert from "node:assert/strict";
import { meetingHasStarted, splitTimelineMeetings } from "../src/timelineMeetings.js";

const now = Date.parse("2026-08-31T10:30:00Z");

test("a meeting moves into the Timeline as soon as its start time arrives", () => {
  assert.equal(meetingHasStarted({ start: "2026-08-31T10:00:00Z" }, now), true);
  assert.equal(meetingHasStarted({ start: "2026-08-31T10:30:00Z" }, now), true);
});

test("future and all-day meetings remain in the upcoming band", () => {
  const current = { subject: "Target Meeting", start: "2026-08-31T10:00:00Z" };
  const future = { subject: "HR Social Media", start: "2026-08-31T14:00:00Z" };
  const allDay = { subject: "Holiday", start: "2026-08-31T00:00:00Z", all_day: true };
  const split = splitTimelineMeetings([current, future, allDay], now);
  assert.deepEqual(split.started, [current]);
  assert.deepEqual(split.upcoming, [future, allDay]);
});
