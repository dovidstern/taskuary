---
title: "The hard part of coding agents is everything before the prompt"
published: false
description: "Five engineering lessons from building a local inbox that turns messy inbound work into reviewed coding-agent sessions."
tags: ai, opensource, productivity, python
---

> Editorial note: this draft was prepared with AI assistance and checked against the Taskuary
> source and documentation on 2026-08-31. It is suitable only for a publication that permits
> disclosed AI-assisted product writing. Do not paste it into Hacker News comments or DEV
> Community. Both platform notes appear after the article.

Coding agents are increasingly good once they are inside a repository with a concrete task.
My bottleneck was everything that happened before that moment.

The work did not arrive as a careful prompt. It arrived as an email with a long reply chain, a
chat message, an issue, an alert, or a report somebody needed to notice. I still had to decide
whether it was real work, collect the relevant context, choose a repository, start the right
tool, watch what it changed, and carry the result back to wherever the request began.

I built [Taskuary](https://github.com/ldbumble/taskuary) to explore that missing layer. It is a
free, MIT-licensed, local-first inbox that sits in front of coding agents. Building it forced a
few design choices that apply to agent systems more broadly.

## 1. Classify the cost, not the topic

An early temptation is to route work by nouns. GitHub goes to a coding agent. Email goes to a
reply writer. Reports go to a dashboard.

That breaks almost immediately. An email can contain a production bug. A GitHub notification
can be informational noise. A chat question might need a one-line answer or three hours of
repository work.

Taskuary instead begins with the cost of the response:

- `task`: something must be investigated, changed, produced, or followed through;
- `reply_only`: a written answer settles the request and no work sits behind it;
- `fyi`: nothing is being asked of the owner.

Only after deciding that an item is a task does the system choose a work path. Repository work
can enter a coding CLI. Research, marketing, and other work can enter a general assistant
session. Information stays on the timeline without consuming an agent slot.

The useful lesson is that routing categories should describe consequences. When a label decides
whether a real process starts, the prompt must explain that cost. Otherwise the model optimizes
for semantic resemblance and quietly creates expensive mistakes: questions become projects,
FYIs become interruptions, and obligations disappear into the archive.

## 2. Context and authority are different things

Giving an agent more context can improve its work. Giving it more authority changes the risk.
Those should not be the same switch.

A Taskuary coding session can receive the original thread, relevant history with the sender,
related closed tasks, owner-written rules, learned preferences, and repository-specific facts.
Knowledge-base passages are explicitly treated as evidence, not instructions. That distinction
matters because an indexed document or inbound message should not be able to rewrite the rules
of the system that reads it.

The authority boundary is separate. An agent may inspect files, edit the checkout, and run tests
within the configured workflow. Sending a reply, pushing a branch, commenting on an issue,
closing work, or releasing software remains a review decision.

This produces a useful asymmetry: make context rich and authority narrow. The agent gets enough
information to do serious work without inheriting every external capability of the person who
owns the accounts.

## 3. The result needs evidence, not a success sentence

"Done" is not a useful interface between an agent and a reviewer.

The reviewer needs to know which files changed, which tests ran, which attempts failed, which
checks could not run, and whether the working tree contains somebody else's work. Taskuary
therefore treats the terminal transcript, changed-file list, test evidence, and missing evidence
as part of the result. Reviews and other important actions are also written to a hash-chained
audit history.

This is not a claim that a hash chain makes an application secure, or that a passing test proves
a change correct. It solves a smaller and more practical problem: the handoff should preserve
enough evidence for a human to make a decision without reconstructing the entire session.

Agent UX often focuses on the prompt box. In day-to-day use, the more important interface may be
the receipt.

## 4. Parallel agents need social rules as well as process isolation

Running several sessions is easy when each gets an isolated repository clone. It is harder when
they share the checkout a developer is already using.

Taskuary maintains a small blackboard for that case. A new session is told which other tasks are
running in the same checkout and which files they have actually modified. If a new task is likely
to touch the same files, it can wait behind the earlier session. The first agent has control of
its files, and later agents are told not to edit, revert, stash, or commit them.

This does not eliminate conflicts. It makes ownership visible before a conflict becomes a Git
problem. That is an important distinction: coordination is partly a scheduling problem and
partly a communication problem. A second agent that knows another session owns a file can often
make progress elsewhere without needing a separate worktree.

## 5. "Local-first" needs a threat model, not a badge

Taskuary stores its own state in local SQLite and binds its server to localhost by default. It
can use Ollama or another local OpenAI-compatible model. Those are useful properties, but they do
not make every configured workflow offline.

An Outlook connector still talks to Microsoft. A GitHub connector still talks to GitHub. A cloud
AI provider receives the content sent to it. Docker runs the web application, while coding CLIs
and the optional WhatsApp bridge remain host programs.

The precise claim is therefore local-first: the application and its state live with the user,
and the user chooses the services it connects to. Precision is more valuable than stretching
"local" until it no longer tells the reader anything.

## What is still unresolved

Taskuary is at v0.3.1. The core funnel, live sessions, review queue, and reports are in daily use,
but it is early and breaking changes are possible before 1.0. Development happens mostly on
Windows; macOS and Linux are in CI but may still expose rough edges in terminals and desktop
integration.

The harder open questions are product questions:

- How much history improves a task before it becomes distracting?
- Which external actions can ever earn limited autonomy, and how is that trust revoked?
- When does one combined timeline reduce handoff loss, and when does it become another alert
  sink?
- What evidence makes an agent's result reviewable without making every review exhaustive?

Those questions are why the project is open source now rather than after they are supposedly
settled.

If your coding-agent workflow begins in an inbox, issue tracker, or alerting system rather than
at a prompt, I would value your view on one boundary: **what should an agent be allowed to do
locally, and which actions must always come back to a person?**

The repository, screenshots, install paths, and current limitations are at
[github.com/ldbumble/taskuary](https://github.com/ldbumble/taskuary).

## Publication notes

### Personal or project development blog

Keep the disclosure at the top, verify the version and limitations immediately before
publishing, and use the Timeline screenshot as the cover image. If the site supports a canonical
URL, make the original project-blog URL canonical before cross-posting elsewhere.

### DEV Community

Do **not** paste or lightly edit this article into DEV. DEV currently requires disclosure for
AI-assisted writing and says AI-assisted articles should not promote a business, program, or
course. Its newer editor also offers explicit AI-disclosure tiers.

For a compliant DEV article, Uri should write a new piece independently, from his own experience,
without using sentences from this draft. A useful human-written structure would be:

1. one real inbound request that exposed the pre-prompt bottleneck;
2. one technical decision from the implementation;
3. one decision that failed or changed during development;
4. a small, reusable pattern readers can apply to their own agent workflow;
5. a question that invites peers to compare designs.

The article should teach the pattern rather than launch the product. Link Taskuary only as the
open-source implementation if that remains secondary to the lesson. Choose the editor's AI
disclosure honestly; using generated drafting or major AI editing means it is not "Hand
Written." Uri should also write all DEV comments without AI assistance.

Check these immediately before publishing:

- [DEV content policy](https://dev.to/terms#section-content-policy)
- [DEV AI-assisted article guidelines](https://dev.to/guidelines-for-ai-assisted-articles-on-dev/)
- [DEV writing and scheduling help](https://dev.to/help/writing-editing-scheduling)
- [DEV editor guide](https://dev.to/p/editor_guide)

### Hacker News

Do not paste any part of this draft into a Hacker News submission or comment. Use the separate
[Hacker News launch brief](hacker-news-launch-brief.md) and write every word there by hand.
