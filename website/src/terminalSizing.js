// Return the new PTY geometry only when it actually changed. ResizeObserver may report the same
// box repeatedly; forwarding duplicates makes full-screen terminal apps repaint for no reason.
export const changedTerminalSize = (previous, rows, cols) => {
  const current = `${rows}x${cols}`;
  return current === previous ? null : current;
};

// A mounted task pane is kept in the DOM while another app tab is open. display:none reports
// a zero-sized box; fitting and forwarding that transient geometry makes a full-screen TUI
// repaint once while hidden and again when the owner returns.
export const usableTerminalBox = (width, height) => width >= 80 && height >= 40;

// FitAddon can land exactly on a fractional cell boundary that the browser then rounds down when
// painting. Reserve one row so a full-screen TUI's status/prompt line is always inside the pane.
// This is shared by Claude, Codex and every other CLI rendered through xterm.
export const safeTerminalRows = (rows) => Math.max(2, Math.floor(rows || 0) - 1);

// The server barrier and xterm parser are independent. Seeing either one alone is not enough
// to uncover a replaying pane - and a pane already uncovered is never "revealed" again: the
// reveal focuses the terminal, so re-running it on every live frame stole the keyboard from
// whatever the owner was typing into.
export const canRevealTerminal = (readySeen, pendingWrites, lifted = false) => !lifted && !!readySeen && pendingWrites === 0;
