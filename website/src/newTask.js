// WHO works a new task is decided by one box: the repository picker. A repository means a CLI
// agent in that checkout - a terminal, on the board. "General - no repository, just a question
// to answer" means the assistant's own chat on the Tasks tab (Kind general -> GeneralWorkspace).
// Filing a general question as a coding task is what opened it in a terminal instead, so the
// rule lives here, on its own, where it can be tested.
export const NO_REPO = "none";

// the picker's value as the API wants it: a repository, or nothing at all
export const repoOf = (pick) => (pick && pick !== NO_REPO ? pick : null);

export const planTask = (pick, how) => {
  const repo = repoOf(pick);
  return { repo, kind: repo ? "coding" : "general", chat: !repo,
    tags: repo ? `repo:${repo}` : null, start: how === "live" };
};
