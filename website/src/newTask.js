// WHO works a new task is decided by one box: the repository picker. A repository means a CLI
// agent in that checkout - a terminal, on the board. "General - no repository, just a question
// to answer" means the assistant's own chat on the Tasks tab (Kind general -> GeneralWorkspace).
// Filing a general question as a coding task is what opened it in a terminal instead, so the
// rule lives here, on its own, where it can be tested.
export const NO_REPO = "none";

// the picker's value as the API wants it: a repository, or nothing at all
export const repoOf = (pick) => (pick && pick !== NO_REPO ? pick : null);

// how: "live" (an agent starts now), "file" (nobody starts), or "terminal" - which is "live"
// for a question you would rather work in a CLI than in the chat. Asked for explicitly, because
// a General task landing in a terminal by ACCIDENT is the bug this module exists to stop.
export const planTask = (pick, how) => {
  const repo = repoOf(pick);
  const chat = !repo && how !== "terminal";
  return { repo, kind: chat ? "general" : "coding", chat,
    tags: repo ? `repo:${repo}` : null, start: how === "live" || how === "terminal" };
};
