# Taskuary launch kit

Prepared 2026-08-31. This is a review document, not permission to publish. Every post,
comment, submission, and reply still requires Uri's approval.

## The story to tell

Taskuary is not another chat box for a coding model. It handles the work on both sides of
the prompt:

1. Work arrives in mail, chat, issues, alerts, and reports.
2. Triage decides whether each item is a task, a reply, or FYI.
3. A real task receives its thread, relevant history, owner rules, and repository context.
4. A coding CLI works in the owner's checkout while Taskuary streams the session and records
   its evidence.
5. Sending, pushing, commenting, closing, and releasing remain approval decisions.

The short positioning line is: **the local inbox in front of your coding agents.** The more
specific explanation is: **Taskuary turns messy inbound work into scoped agent sessions and
brings the result back for human review.**

## Recommended sequence

Do not launch everywhere on one day. One useful conversation is worth more than several
identical link drops.

1. Start with the current **r/selfhosted New Project Megathread**. It is the safest place to
   test whether deployment and privacy claims are clear. Use Draft 2 in the
   [Reddit launch plan](reddit-launch-plan.md).
2. Three or more days later, use the standalone **r/opensource** post. Ask about the approval
   boundary and connector architecture, not for stars. Use Draft 1 in the Reddit plan.
3. After fixing any README or first-run confusion those readers find, submit **Show HN**.
   Hacker News requires the submission text and comments to be written by the human author;
   use the [HN writing brief](hacker-news-launch-brief.md), not generated copy.
4. Publish the [developer blog draft](developer-blog-draft.md) on a site whose policy permits
   disclosed AI-assisted writing. For DEV Community, do not paste that draft: its current
   guidelines disallow AI-assisted articles that promote a product. Write the DEV version
   independently from personal experience, using the compliance notes in that file.
5. Use the **r/ChatGPTCoding** and **r/codex** weekly threads only after the general launch.
   Their drafts ask a narrower question about agent handoffs and context boundaries.

Re-read every community's live rules and pinned thread immediately before posting. If the
format or flair has changed, wait and adapt rather than trying a neighboring category.

## Asset and link map

Use one destination per post. For product launches, the repository is the best destination
because readers can inspect and run the project without signing up.

- Repository: `https://github.com/ldbumble/taskuary`
- No-signup install: `pip install taskuary`, then `taskuary`
- Docker: clone the repository, run `docker compose up`, then open
  `http://127.0.0.1:7787`
- Windows: the latest release includes a single-file `Taskuary.exe`
- Primary demo: `docs/hero.gif`
- Timeline screenshot: `docs/screenshot-timeline-crop.png`
- Agent-session screenshot: `docs/screenshot-board.png`
- Multi-session screenshot: `docs/screenshot-wall.png`
- Assistant screenshot: `docs/screenshot-assistant.png`

For a text post that permits one image, use the hero GIF or Timeline screenshot. Do not attach
a gallery unless the community expects one; the README already contains the visual tour.

## Truth bank

These claims are supported by the repository and can be used consistently across posts:

- Taskuary is free, MIT-licensed, and currently at v0.3.1.
- It is early, used daily, and may have breaking changes before 1.0.
- Its own state is stored locally in SQLite.
- It can use a local Ollama or OpenAI-compatible model, but connected services and configured
  cloud AI providers still use the network. Say **local-first**, never **fully offline**.
- It supports Claude Code, Codex, Gemini, Cursor, and Copilot CLI presets, plus configurable
  CLIs that accept a prompt on standard input.
- The Python application runs on Windows, macOS, and Linux. Most daily development happens on
  Windows, so macOS and Linux may have rough edges.
- Docker runs the web application. Coding CLIs and the optional WhatsApp bridge remain on the
  host.
- The server binds to localhost by default. A token is required before exposing it to a LAN.
- High-impact outbound actions remain approval-gated.
- The audit history is hash-chained, and reviews retain changed files, tests, attempts, and
  missing evidence.
- Concurrent sessions in one checkout are shown each other's modified files; likely overlap
  can wait behind the earlier session.

Do not call the project production-ready, enterprise-ready, autonomous, private by default in
every configuration, or a replacement for human review.

## Comment posture

- Disclose the maintainer relationship immediately.
- Answer the exact question with implementation detail or say that it is not built yet.
- Treat skepticism about mail access, AI providers, secrets, and auto-approval as reasonable.
- When somebody reports a bug, ask for the install method, operating system, expected result,
  and actual result. Do not turn the thread into support theater.
- Do not ask for votes, stars, reposts, or supportive comments.
- Do not use generated replies on Hacker News or DEV Community. Uri should answer there in his
  own words.
- Record repeated confusion as a README or product problem; do not argue the wording into
  clarity one commenter at a time.

## What to measure

The useful signals are not raw impressions:

- Can a new reader explain the product without calling it a task manager or agent wrapper?
- Can somebody install it without maintainer help?
- Which trust boundary blocks adoption: inbound access, model access, local storage, or
  outbound approval?
- Which connector is the first missing dependency for a real workflow?
- Do people complete first-run setup and return with a concrete bug or use case?

After each venue, revise the next post with what was learned. Do not silently change factual
claims between communities.
