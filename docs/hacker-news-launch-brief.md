# Hacker News launch brief

Prepared 2026-08-31. This is deliberately a writing brief, not paste-ready submission copy.
Hacker News currently tells authors to write submission text and comments by hand and not to
use LLM-generated or AI-edited text. Uri must write the final text in his own words.

Nothing here authorizes a submission or a comment.

## Recommended submission

Use **Show HN** and link directly to:

`https://github.com/ldbumble/taskuary`

The repository is the right target because Taskuary is working software that can be installed
without an account or email gate. Do not link the landing page as the primary Show HN URL.

Write a factual title in the standard form:

`Show HN: [project name] - [plain description of what it does]`

The description should express one idea: an inbox that turns inbound work into reviewed coding
agent sessions. Avoid claims such as "revolutionary," "autonomous," "all-in-one," or "the
future of work."

## Write the opening text by hand

Aim for 250-450 words. Use this order, but supply personal language and details yourself:

1. **The trigger.** Describe one real instance when useful work arrived outside the terminal
   and copying the request, history, and repository rules into an agent became the bottleneck.
   Name what was frustrating about the old workflow.
2. **The product.** Explain in two sentences what Taskuary does from arrival to review. Make
   the task/reply/FYI distinction clear.
3. **The non-obvious decision.** Explain why the approval boundary matters. Distinguish what
   an agent may do in a checkout from what Taskuary will not send, push, comment, close, or
   release without review.
4. **The technical shape.** Mention Python/FastAPI, React, SQLite, live PTY sessions, editable
   Markdown operator rules, and the supported CLI agents only if they help explain a decision.
   A component list without a design reason will read like marketing.
5. **How to try it.** Give either the two-command Python route or the Docker route. State that
   Docker does not contain the host coding CLIs.
6. **What is rough.** Say that it is v0.3.1, pre-1.0, developed mostly on Windows, and likely
   to have macOS/Linux rough edges. Add one limitation you personally want feedback on.
7. **The question.** Ask one narrow question that can produce a technical discussion. The best
   candidate is where people draw the authority boundary between an agent's local work and
   consequential external actions.

Do not copy these bullets into Hacker News. They are a fact and memory aid for a human-written
post.

## Facts to have open while writing

- Taskuary combines inbound mail, chats, issues, alerts, and reports on a local timeline.
- Triage produces `task`, `reply_only`, or `fyi`; coding and general tasks then take different
  work paths.
- A coding-task context can contain the thread, relevant sender/topic history, related closed
  work, learned owner preferences, knowledge-base excerpts, and repository rules.
- Coding sessions run in the user's configured checkout through Claude Code, Codex, Gemini,
  Cursor, Copilot, or another stdin-driven CLI.
- The UI streams the terminal and exposes changed files and work evidence.
- Review-gated actions include outbound replies and repository actions such as pushing or
  opening a pull request.
- State is local SQLite. Local models are supported, but connected sources and cloud providers
  still use their networks.
- Install options are pip, Docker, a desktop extra, and a Windows executable.
- The project is free, MIT-licensed, at v0.3.1, and not yet 1.0.

## Likely questions and precise answers

### Is it autonomous?

It automates triage and can start configured agent work, but consequential outbound actions
remain explicit review decisions. Avoid arguing over the word; describe the boundary.

### Is everything local?

Taskuary's application state is local. Ollama can keep model inference local. Mail, chat,
GitHub, Jira, and other connected services still require network access, and a cloud model sees
the content sent to that configured provider.

### Why not use an issue tracker plus an agent CLI?

That combination works once a clean issue exists. Taskuary is for the earlier translation step:
deciding whether an inbound item is work at all, preserving its surrounding context, and
returning the result to the source channel for review.

### Why run agents in a shared checkout?

That is how many developers already work and it makes the live diff inspectable. Taskuary shows
new sessions which files peers have modified and can queue likely overlaps, but it does not claim
to eliminate merge conflicts.

### What can I try without giving it my mailbox?

The repository includes install instructions and the UI can be run locally. Be candid about
which useful workflows require a connector; do not imply a polished hosted demo exists.

### How are secrets handled?

Answer only from the current documentation and implementation. Do not make broad security or
encryption claims. The safe published claims are localhost binding by default and token
protection before LAN exposure.

## Submission-day check

- Read the current [Show HN guidelines](https://news.ycombinator.com/showhn.html) and
  [Hacker News guidelines](https://news.ycombinator.com/newsguidelines.html).
- Install from the exact link and commands a reader will see.
- Confirm the repository is public, the screenshots load, and the latest release link works.
- Search HN for any previous Taskuary submission and link it if one exists.
- Use a personal HN account, not a product-named account.
- Write the title, opening text, and every reply without AI generation or AI editing.
- Do not ask friends, users, or alternate accounts to vote or add booster comments.
- Stay available for technical questions after submission.
- If the post gets little attention, do not delete and repost it.

## Sources

- [Show HN guidelines](https://news.ycombinator.com/showhn.html)
- [Hacker News guidelines](https://news.ycombinator.com/newsguidelines.html)
- [HN moderator's Show HN presentation notes](https://news.ycombinator.com/item?id=22336638)
