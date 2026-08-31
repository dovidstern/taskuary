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
// * the opening question is NOT passed through here at all any more. Handing it across the
//   navigation lost it twice - once to that stale `detail`, once to the effect that cleared it
//   in the same commit that set it. It rides on the task as a tag instead (newTask.js), and the
//   chat reads it when it opens.
export const GENERAL_KINDS = new Set(["general", "research", "marketing", "triage", "assistant"]);

export const isGeneralKind = (kind) => GENERAL_KINDS.has(String(kind || "general").toLowerCase());

/** What the Tasks tab should do right now. `detail` is whatever is loaded, stale or not. */
export const autostartPlan = ({ autostart, selected, detail, hasSession }) => {
  const task = detail?.task?.TaskId === selected ? detail.task : null;   // never the previous one
  if (!autostart || autostart.taskId !== selected || !task) return { do: "wait" };
  // nothing to START for a general task: the chat asks its own opening question, off the tag
  // the Board put on the task (newTask.js). Handing it a seed through here is what lost the
  // question twice - to a stale `detail`, and to the effect that cleared it.
  if (isGeneralKind(task.Kind)) return { do: "chat" };
  // ...a CLI is different: a second terminal on one task is a second agent in one checkout
  return hasSession ? { do: "wait" } : { do: "terminal" };
};
