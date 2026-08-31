// A full-screen CLI redraw reaches the browser as several websocket messages a few
// milliseconds apart. Parsing every fragment separately lets Codex's repaint backlog
// outrun the owner's keystrokes. Fold everything received before the next browser paint
// into one ordered xterm write; ready/exit can flush the batch immediately.
export const terminalOutputBatcher = (onBatch, schedule = requestAnimationFrame, cancel = cancelAnimationFrame) => {
  let data = "";
  let replay = false;
  let frame = null;

  const flush = () => {
    if (frame !== null) cancel(frame);
    frame = null;
    if (!data) return;
    const batch = { data, replay };
    data = "";
    replay = false;
    onBatch(batch);
  };
  const push = (chunk, isReplay = false) => {
    data += String(chunk || "");
    replay ||= !!isReplay;
    if (frame === null) frame = schedule(flush);
  };
  const dispose = () => {
    if (frame !== null) cancel(frame);
    frame = null;
    data = "";
    replay = false;
  };
  return { push, flush, dispose };
};
