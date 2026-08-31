import test from "node:test";
import assert from "node:assert/strict";
import { terminalOutputBatcher } from "../src/terminalOutput.js";

test("terminal redraw fragments become one ordered xterm write per paint", () => {
  const scheduled = [];
  const batches = [];
  const batcher = terminalOutputBatcher((batch) => batches.push(batch), (fn) => { scheduled.push(fn); return scheduled.length; }, () => {});

  batcher.push("first ");
  batcher.push("second ");
  batcher.push("third", true);
  assert.equal(scheduled.length, 1);
  assert.deepEqual(batches, []);

  scheduled.shift()();
  assert.deepEqual(batches, [{ data: "first second third", replay: true }]);
});

test("ready can flush pending output before the scheduled paint", () => {
  const scheduled = [];
  const batches = [];
  const batcher = terminalOutputBatcher((batch) => batches.push(batch), (fn) => { scheduled.push(fn); return scheduled.length; }, () => {});

  batcher.push("live screen");
  batcher.flush();
  assert.deepEqual(batches, [{ data: "live screen", replay: false }]);
});
