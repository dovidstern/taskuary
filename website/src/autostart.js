// "New task → start on it" lands on the Tasks tab, and something there has to decide WHAT to
// start: a CLI terminal, or the assistant's chat with the owner's prompt as its first message.
//
// It is one decision made from four moving parts, and getting it wrong is silent - a chat that
// opens empty looks exactly like a chat you have not typed into yet. Two ways it went wrong,
// both here rather than in a component, so both stay fixed:
//
// * `detail` is NOT cleared when the selected task changes - it holds the PREVIOUS task until
//   the fetch returns. Reading a Kind, a Summary or a repo off it in that window is reading
//   somebody else's task.
// * the seed has to belong to a task. Clearing it "when the selection changes" raced the very
//   selection change that produced it and ate the prompt before the chat ever mounted.
export const GENERAL_KINDS = new Set(["general", "research", "marketing", "triage", "assistant"]);

export const isGeneralKind = (kind) => GENERAL_KINDS.has(String(kind || "general").toLowerCase());

/** What the Tasks tab should do right now. `detail` is whatever is loaded, stale or not. */
export const autostartPlan = ({ autostart, selected, detail, hasSession }) => {
  const task = detail?.task?.TaskId === selected ? detail.task : null;   // never the previous one
  if (!autostart || autostart.taskId !== selected || !task) return { do: "wait" };
  if (isGeneralKind(task.Kind)) {
    // the chat's own thread decides whether the question has already been asked, so a session
    // that already exists is no reason to stay silent
    return { do: "chat", seed: { taskId: selected, text: String(task.Summary || "").trim() } };
  }
  // ...a CLI is different: a second terminal on one task is a second agent in one checkout
  return hasSession ? { do: "wait" } : { do: "terminal" };
};

/** The seed to hand the chat: only ever the one that came with THIS task. */
export const seedFor = (seed, selected) => (seed && seed.taskId === selected ? seed.text : "");
