# The Taskuary Agent

This is a separate agent from the coding agent in a task. Its job is to operate and adapt
Taskuary itself: find work, explain why something is surfaced, organize tasks, prepare actions,
and help the owner change how the app behaves. Coding sessions remain bounded to a repository
and run through the configured coding CLI in Taskuary's terminal workspace.

## Recommendation

Build the Taskuary Agent on [CopilotKit](https://github.com/CopilotKit/CopilotKit) for its React
agent UI and use [AG-UI](https://docs.copilotkit.ai/ag-ui/introduction) as the contract to a new
FastAPI agent endpoint. Use CopilotKit headlessly: Taskuary owns the pixels and supplies a small
allowlist of task-native components instead of adopting the stock CopilotKit chat skin.

Do not put ACP between this agent and Taskuary. ACP is a coding-agent/client protocol. AG-UI is
the agent/user/app protocol and already models streamed messages, tool calls, shared state,
attachments, interruption, and human approval.

```text
                         Taskuary UI
               selected task · filters · current view
                              │
                    CopilotKit headless React
                              │ AG-UI / SSE
                              ▼
               Taskuary Agent (FastAPI, local)
                  │            │             │
             read tools   proposed writes   profile/skills
                  │            │ approval         │
                  └──────── Taskuary service layer ┘
                                      │
                         SQLite · connectors · sessions
                                      │
                       direct CLI terminal
                      (coding workspaces only)
```

The existing service layer remains authoritative. The agent never receives a database handle
and never writes tables directly.

## What the experience looks like

The agent is a drawer available from Timeline, Tasks, Wall, Review, and Settings. It can expand
into a full canvas for larger results. The drawer header always shows its scope, for example:

> Looking at TQ-0031 + its GitHub thread · read access · 2 actions need approval

It is contextual without being mysterious:

- On Tasks, it receives the selected task, visible search/filter, and related message IDs.
- On Wall, it receives the visible session IDs and their public status—not terminal keystrokes
  or unrelated transcripts.
- On Timeline, it receives the selected row and the IDs of visible results, not the whole inbox.
- On Settings, it can inspect the active agent profile and propose a profile patch.

The initial component allowlist should be small and controlled:

- `TaskResults` — searchable task rows with open/select actions.
- `TimelineEvidence` — the messages that support an answer.
- `DraftReview` — editable text with approve, reject, and save-draft actions.
- `ActionPlan` — proposed mutations, each with its permission level.
- `AgentProfileDiff` — instructions, tools, or skills before/after.
- `SessionLauncher` — repository, coding CLI, and model.
- `ConnectorHealth` — read-only status and a link to the existing connector card.

The model chooses a component and its typed data; it does not generate arbitrary React or HTML.
That keeps the design coherent and makes the security boundary reviewable.

## Customization through the agent

An agent profile is local data with explicit fields:

| Field | Meaning |
| --- | --- |
| Name and avatar | How the agent appears in the app |
| Model | Any model already configured in Taskuary |
| Instructions | Voice, priorities, and standing behavior |
| Skills | Versioned instruction packs with declared tools and inputs |
| Tools | Per-tool grants: off, read, propose, or act |
| Approval policy | Which proposed actions need a human checkpoint |
| Context policy | Which views/data classes it may inspect |

The profile is editable in Settings, but the interesting path is conversational. “Be shorter,
never change GitHub labels, and add a weekly-planning skill” produces an `AgentProfileDiff`.
Nothing changes until the owner accepts the diff. The agent cannot silently broaden its own
tools, context, or approval policy.

Skills should be boring, portable folders: a complete `SKILL.md`, optional references/templates,
a manifest that declares tools and inputs, and a version. A skill may narrow its permissions but
cannot grant itself anything the profile lacks. This supports personal and shared skills without
turning natural-language instructions into an invisible capability system.

## Tool and approval boundary

Start with tools that call existing Taskuary functions rather than HTTP-looping back into the app.

| Level | Examples | Behavior |
| --- | --- | --- |
| Read | search tasks, read a task/thread, list reviews, inspect session status | Runs immediately and renders evidence |
| Local edit | create task, change status/tags, edit a draft, queue a prompt | Shows a compact proposal; owner may allow selected low-risk tools |
| External write | send reply, comment on GitHub, start a coding workspace | Always pauses for review in the first release |
| High impact | push/deploy, delete, change connector credentials, widen its own grants | Not exposed initially |

Every mutation goes through the same policy, audit, and review code as a button click. Approval is
an AG-UI interrupt with the exact tool name, arguments, affected records, and resulting action.
The agent resumes from that checkpoint after approve/edit/reject rather than starting over.

## Shared state

AG-UI shared state should contain a compact, typed view model—not a copy of Taskuary:

```json
{
  "route": "tasks",
  "selectedTaskId": 31,
  "visibleTaskIds": [31, 18, 9],
  "filters": { "taskState": "in_progress", "query": "PR 31" },
  "draftAction": null,
  "activeStep": "idle"
}
```

The browser can update selection and filters immediately. The agent can propose navigation or a
draft action. Persistent facts are re-read through tools, so stale shared state cannot overwrite
newer database state.

## Backend shape

Add one authenticated endpoint, `POST /api/taskuary-agent/run`, accepting `RunAgentInput` and
returning AG-UI events as SSE. The official Python `ag-ui` types and `EventEncoder` work directly
with FastAPI; no second Node server is required. A run should:

1. Resolve the saved agent profile and current Taskuary model provider.
2. Validate the client-supplied context IDs against the current owner/session.
3. stream a state snapshot and response/tool events;
4. execute read tools or emit an interrupt for a proposed mutation;
5. persist the thread and audit any accepted action locally.

The model/tool loop can initially reuse Taskuary's existing provider abstraction. Adopting
LangGraph, PydanticAI, or another agent framework later does not affect the UI as long as the
endpoint continues to speak AG-UI.

## CopilotKit integration caveat

CopilotKit's documented production `selfManagedAgents` path is part of its commercial
Intelligence offering, while `agents__unsafe_dev_only` is explicitly for local prototypes.
Taskuary should therefore do a localhost-only spike with the latter, then choose one of two
shipping paths before making the feature default:

1. use the open-source Copilot Runtime and route the local FastAPI AG-UI agent through it; or
2. keep the open AG-UI client/runtime connection and build the final headless shell without a
   feature that requires a commercial license.

That decision does not block the agent or protocol design, but it should block a production
dependency commitment.

## Delivery slices

1. **Read-only copilot:** drawer, local thread persistence, current-view context, task/timeline
   search, evidence components, no mutation tools.
2. **Proposed actions:** create/update task, draft reply, queue prompt, and session launch behind
   explicit approval cards and audit entries.
3. **Self-customization:** profile editor, profile diffs, installed skills, tool/context grants.
4. **App collaboration:** shared filters and selection, richer controlled UI, resumable interrupts.
5. **Optional orchestration:** delegate coding work to a configured CLI terminal and monitor it;
   never merge the coding conversation into the Taskuary Agent's own thread.

The first slice is successful when “find the old PR 31 task and tell me what is blocking it”
returns the right task and evidence, can open it in place, and cannot change anything. The second
is successful when “reopen it and ask an agent to review the new commits” produces two inspectable
actions—task update and session launch—and executes only what the owner approves.
