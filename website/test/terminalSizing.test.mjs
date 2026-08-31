import test from "node:test";
import assert from "node:assert/strict";
import { canRevealTerminal, changedTerminalSize, safeTerminalRows, usableTerminalBox } from "../src/terminalSizing.js";

test("unchanged terminal geometry does not produce another PTY resize", () => {
  assert.equal(changedTerminalSize("32x110", 32, 110), null);
  assert.equal(changedTerminalSize("32x110", 33, 110), "33x110");
  assert.equal(changedTerminalSize("32x110", 32, 111), "32x111");
});

test("hidden and half-laid-out panes never resize the PTY", () => {
  assert.equal(usableTerminalBox(0, 0), false);
  assert.equal(usableTerminalBox(900, 0), false);
  assert.equal(usableTerminalBox(79, 500), false);
  assert.equal(usableTerminalBox(900, 500), true);
});

test("a fitted terminal reserves its final visible row for TUI chrome", () => {
  assert.equal(safeTerminalRows(50), 49);
  assert.equal(safeTerminalRows(3), 2);
  assert.equal(safeTerminalRows(0), 2);
});

test("the curtain waits for both the server repaint barrier and every xterm write", () => {
  assert.equal(canRevealTerminal(false, 0), false);
  assert.equal(canRevealTerminal(true, 2), false);
  assert.equal(canRevealTerminal(true, 0), true);
});

test("a live frame after the reveal never lifts the curtain (and refocuses the terminal) again", () => {
  assert.equal(canRevealTerminal(true, 0, false), true);      // the one reveal
  assert.equal(canRevealTerminal(true, 0, true), false);      // every later completed write
  assert.equal(canRevealTerminal(true, 1, true), false);
});
