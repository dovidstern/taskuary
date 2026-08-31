import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AssistantRuntimeProvider, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useLocalRuntime,
} from "@assistant-ui/react";
import { Alert, Box, Button, Chip, CircularProgress, IconButton, MenuItem, Select, TextField, Typography } from "@mui/material";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import CloseIcon from "@mui/icons-material/Close";
import SendIcon from "@mui/icons-material/ArrowUpward";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import EventRepeatIcon from "@mui/icons-material/EventRepeat";
import TerminalIcon from "@mui/icons-material/Terminal";
import ViewDayIcon from "@mui/icons-material/ViewDay";
import FunctionsIcon from "@mui/icons-material/Functions";
import api from "./api.js";
import { streamAssistant, toolTarget } from "./assistantStream.js";
import { wantsAsk, withoutAsk } from "./newTask.js";
import { Md } from "./md.jsx";
import { SessionPane, TerminalPane } from "./TerminalView.jsx";
import SemanticPanel from "./SemanticPanel.jsx";
import { BORDER, DIM, FAINT, INK, PANEL, PANEL2, mono } from "./theme.jsx";
import "./generalWorkspace.css";

const savedView = () => localStorage.getItem("taskuary_general_view") || "assistant";
const errText = (e) => e?.response?.data?.detail || e?.message || "The assistant could not respond.";
const textOf = (message) => (message?.content || []).filter((p) => p.type === "text").map((p) => p.text).join("\n").trim();
const initial = (messages) => (messages || []).map((m) => ({
  ...m,
  createdAt: m.createdAt ? new Date(String(m.createdAt).replace(" ", "T") + (String(m.createdAt).includes("Z") ? "" : "Z")) : undefined,
}));

const AssistantText = ({ text }) => <Md text={text} />;
const AssistantReasoning = ({ text }) => text ? (
  <details className="tq-aui-progress" open>
    <summary>Agent progress</summary>
    <div>{text}</div>
  </details>
) : null;
const AssistantTool = ({ toolName, args, result, isError }) => {
  const state = isError ? "error" : result === undefined ? "running" : "complete";
  const target = toolTarget(args);
  return (
    <details className={`tq-aui-tool tq-aui-tool-${state}`}>
      <summary><span className="tq-aui-tool-dot" /> <b>{toolName}</b>{target && <span>{target}</span>}<em>{state}</em></summary>
      <pre>{JSON.stringify({ input: args, ...(result?.output ? { output: result.output } : {}) }, null, 2)}</pre>
    </details>
  );
};
const UserMessage = () => (
  <MessagePrimitive.Root className="tq-aui-message tq-aui-user">
    <div className="tq-aui-role">you</div>
    <div className="tq-aui-user-bubble"><MessagePrimitive.Parts /></div>
  </MessagePrimitive.Root>
);
const AssistantMessage = () => (
  <MessagePrimitive.Root className="tq-aui-message tq-aui-agent">
    <div className="tq-aui-role">assistant</div>
    <div className="tq-aui-agent-body">
      <MessagePrimitive.Parts components={{ Text: AssistantText, Reasoning: AssistantReasoning,
        tools: { Fallback: AssistantTool } }} />
    </div>
  </MessagePrimitive.Root>
);

function AssistantThread({ task, messages, onAsked, selectionRef, attachmentsRef, onSent, onClearAttachments, onAttach, onReport, reportBusy }) {
  const modelAdapter = useMemo(() => ({
    async *run({ messages: runMessages, abortSignal }) {
      const prompt = textOf([...runMessages].reverse().find((m) => m.role === "user"));
      const selected = selectionRef.current;
      const body = {
        text: prompt,
        pick: selected.connectorId || null,
        model: selected.model || null,
        attachments: attachmentsRef.current.map((a) => a.path),
      };
      const tools = new Map();
      const progress = [];
      let structuredSeen = false;
      const content = (reply) => [
        ...tools.values(),
        ...(progress.length ? [{ type: "reasoning", text: progress.join("\n\n") }] : []),
        ...(reply ? [{ type: "text", text: reply }] : []),
      ];
      for await (const event of streamAssistant(task.TaskId, body, abortSignal)) {
        if (event.type === "tool_call") {
          structuredSeen = true;
          const id = event.detail?.tool_call_id || `${event.name}-${tools.size}`;
          const args = event.detail?.args || {};
          tools.set(id, { type: "tool-call", toolCallId: id, toolName: event.name || "tool", args,
            argsText: JSON.stringify(args) });
          yield { content: content() };
        } else if (event.type === "tool_result") {
          const old = tools.get(event.name);
          if (old) tools.set(event.name, { ...old, result: { output: event.detail?.result || "" },
            isError: !!event.detail?.is_error });
          yield { content: content() };
        } else if (event.type === "start") {
          progress.push(`Started ${event.session?.provider || "the selected agent"}`);
          yield { content: content() };
        } else if (event.type === "progress" && event.detail) {
          structuredSeen = true;
          progress.push(String(event.detail));
          yield { content: content() };
        } else if (event.type === "live" && !structuredSeen && event.detail) {
          // Custom/Gemini/Aider CLIs may only provide line-oriented stdout. It is still live
          // work and must not leave a blank pane merely because it lacks Claude/Codex JSON.
          progress.push(String(event.detail));
          yield { content: content() };
        } else if (event.type === "error") {
          throw new Error(event.error || "The agent stopped without an answer.");
        } else if (event.type === "done") {
          onClearAttachments(); onSent(event.payload);
          yield { content: content(event.reply) };
        }
      }
    },
  }), [attachmentsRef, onClearAttachments, onSent, selectionRef, task.TaskId]);
  const runtime = useLocalRuntime(modelAdapter, { initialMessages: initial(messages) });
  /* "New task for the agent" with no repository: the prompt the owner typed is the first thing
     said here, appended through the same streaming runtime as anything they type - so they watch
     the answer arrive instead of finding a task with their own words sitting in it, unanswered.

     The question is read off the TASK (newTask.js: the ask tag), never handed in as a prop: two
     earlier attempts passed it across the navigation and lost it to a re-render both times.
     Only into an EMPTY thread, and only once - the tag is stripped as it is asked, so a reload
     never re-asks and a chat opened an hour later still gets the question. */
  const asked = useRef(false);
  useEffect(() => {
    const text = String(task.Summary || '').trim();
    if (asked.current || messages?.length || !text || !wantsAsk(task)) return;
    asked.current = true;
    onAsked?.();
    runtime.thread.append(text);
  }, [task, messages, runtime, onAsked]);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="tq-aui-thread">
        <ThreadPrimitive.Viewport className="tq-aui-viewport">
          {!messages?.length && (
            <div className="tq-aui-welcome">
              <SmartToyIcon sx={{ fontSize: 22 }} />
              <div>
                <div className="tq-aui-welcome-title">Work on this with your assistant</div>
                <div className="tq-aui-welcome-copy">Research, plan, write, analyze, or coordinate. This conversation stays on the task.</div>
              </div>
            </div>
          )}
          <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
          {messages?.some((m) => m.role === "assistant") && (
            <div className="tq-aui-report-action">
              <div><b>Worth running again?</b><span>Creates a daily report from this workflow; adjust its cadence in Reports.</span></div>
              <Button size="small" variant="outlined" startIcon={<EventRepeatIcon sx={{ fontSize: 15 }} />}
                disabled={reportBusy} onClick={onReport}>{reportBusy ? "Creating…" : "Make recurring report"}</Button>
            </div>
          )}
        </ThreadPrimitive.Viewport>
          <div className="tq-aui-footer">
            {!!attachmentsRef.current.length && (
              <div className="tq-aui-attachments">
                {attachmentsRef.current.map((a) => (
                  <Chip key={a.path} size="small" icon={<AttachFileIcon />} label={a.name}
                    onDelete={() => onClearAttachments(a.path)} />
                ))}
              </div>
            )}
            <ComposerPrimitive.Root className="tq-aui-composer">
              <IconButton size="small" onClick={onAttach} title="Attach an image" className="tq-aui-attach">
                <AttachFileIcon sx={{ fontSize: 18 }} />
              </IconButton>
              <ComposerPrimitive.Input className="tq-aui-input" placeholder="Tell the assistant what to do next…" />
              <ComposerPrimitive.Cancel className="tq-aui-cancel" aria-label="Stop response"><CloseIcon fontSize="small" /></ComposerPrimitive.Cancel>
              <ComposerPrimitive.Send className="tq-aui-send" aria-label="Send"><SendIcon fontSize="small" /></ComposerPrimitive.Send>
            </ComposerPrimitive.Root>
            <div className="tq-aui-hint">Enter sends · Shift+Enter adds a line · paste or attach an image</div>
          </div>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

export function GeneralWorkspace({ task, onSession, onOpenReports, compact = false }) {
  const [data, setData] = useState(null);
  const [view, setView] = useState(savedView);
  const [connectorId, setConnectorId] = useState("");
  const [model, setModel] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [threadKey, setThreadKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const fileRef = useRef(null);
  const selectionRef = useRef({ connectorId: "", model: "" });
  const attachmentsRef = useRef([]);
  selectionRef.current = { connectorId, model };
  attachmentsRef.current = attachments;

  // asked once, and only once: the marker is cleared on the server as the question goes
  const dropAsk = useCallback(() => {
    api.patch(`/api/tasks/${task.TaskId}`, { Tags: withoutAsk(task.Tags) }).catch(() => {});
  }, [task.TaskId, task.Tags]);

  const accept = useCallback((payload) => {
    setData(payload);
    const current = payload?.providers?.find((p) => String(p.id) === String(payload?.session?.pick));
    const provider = current || payload?.providers?.find((p) => p.label === payload?.session?.provider) || payload?.providers?.[0];
    if (provider) {
      setConnectorId((old) => old || String(provider.id));
      setModel((old) => old || payload?.session?.model || provider.model || "");
    }
    if (payload?.session) onSession?.(payload.session);
  }, [onSession]);

  useEffect(() => {
    let live = true;
    setData(null); setError(""); setAttachments([]);
    api.post(`/api/tasks/${task.TaskId}/assistant/session`, {}).then((r) => live && accept(r.data)).catch((e) => live && setError(errText(e)));
    return () => { live = false; };
  }, [accept, task.TaskId]);

  const chooseView = async (next) => {
    localStorage.setItem("taskuary_general_view", next);
    if (next === "assistant" && view !== "assistant") {
      try {
        const r = await api.get(`/api/tasks/${task.TaskId}/assistant`);
        accept(r.data); setThreadKey((n) => n + 1);
      } catch (e) { setError(errText(e)); }
    }
    setView(next);
  };
  const updateProvider = async (nextId, nextModel = model) => {
    setConnectorId(String(nextId)); setModel(nextModel); setError("");
    try {
      const r = await api.post(`/api/tasks/${task.TaskId}/assistant/session`, { pick: nextId || null, model: nextModel || null });
      accept(r.data);
    } catch (e) { setError(errText(e)); }
  };
  const upload = async (files) => {
    const images = [...(files || [])].filter((f) => /^image\/(png|jpeg|gif|webp)$/.test(f.type));
    if (!images.length) return;
    setUploading(true); setError("");
    try {
      const added = [];
      for (const file of images) {
        const r = await api.post(`/api/tasks/${task.TaskId}/waitroom/image`, file, { headers: { "Content-Type": file.type } });
        added.push({ name: file.name || "pasted image", path: r.data.path });
      }
      setAttachments((old) => [...old, ...added]);
    } catch (e) { setError(errText(e)); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const clearAttachments = useCallback((path) => setAttachments((old) => path ? old.filter((a) => a.path !== path) : []), []);
  const sent = useCallback((payload) => accept(payload), [accept]);
  const makeReport = async () => {
    setError(""); setReportBusy(true);
    try {
      const { data: made } = await api.post(`/api/tasks/${task.TaskId}/assistant/report`, {
        pick: connectorId || null, model: model || null,
      });
      if (onOpenReports) onOpenReports(made.sourceId);
      else setError(`Created “${made.title}” in Reports.`);
    } catch (e) { setError(errText(e)); }
    finally { setReportBusy(false); }
  };
  const pasted = (e) => {
    const images = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
    if (images.length) { e.preventDefault(); upload(images); }
  };

  if (!data && !error) return <Box sx={{ height: 520, display: "grid", placeItems: "center" }}><CircularProgress size={22} /></Box>;
  const session = data?.session;
  return (
    <Box onPaste={pasted} sx={{ border: `1px solid ${BORDER}`, borderRadius: 1.75, overflow: "hidden", bgcolor: PANEL2,
      minHeight: 0, display: "flex", flexDirection: "column",
      ...(compact ? { height: "100%" } : { flex: "1 1 auto" }) }}>
      <Box sx={{ minHeight: 39, px: 1.25, display: "flex", alignItems: "center", gap: 0.8, borderBottom: `1px solid ${BORDER}`, bgcolor: PANEL,
        overflowX: "auto", flexShrink: 0 }}>
        <Box sx={{ width: 7, height: 7, borderRadius: 99, bgcolor: session?.alive ? "#78a17b" : "#c7a258" }} />
        <Typography sx={{ ...mono, fontSize: 10.5, letterSpacing: ".13em", textTransform: "uppercase", color: DIM }}>assistant workspace</Typography>
        <Box sx={{ flex: 1 }} />
        <Select size="small" value={connectorId} displayEmpty onChange={(e) => {
          const provider = data?.providers?.find((p) => String(p.id) === String(e.target.value));
          updateProvider(e.target.value, provider?.model || "");
        }}
          sx={{ height: 27, fontSize: 11.5, minWidth: 130, bgcolor: PANEL2 }}>
          {!data?.providers?.length && <MenuItem value="">No agent connected</MenuItem>}
          {(data?.providers || []).map((p) => <MenuItem key={p.id} value={String(p.id)}>{p.label}</MenuItem>)}
        </Select>
        <TextField size="small" value={model} placeholder="provider default" onChange={(e) => setModel(e.target.value)}
          onBlur={() => connectorId && updateProvider(connectorId, model)} sx={{ width: 150, "& input": { py: 0.55, fontSize: 11.5 } }} />
        <Button size="small" startIcon={<ViewDayIcon sx={{ fontSize: 14 }} />} variant={view === "assistant" ? "contained" : "text"}
          onClick={() => chooseView("assistant")} sx={{ minWidth: 0, fontSize: 11 }}>Assistant</Button>
        <Button size="small" startIcon={<TerminalIcon sx={{ fontSize: 14 }} />} variant={view === "terminal" ? "contained" : "text"}
          onClick={() => chooseView("terminal")} sx={{ minWidth: 0, fontSize: 11 }}>Terminal</Button>
        {/* what it is ALLOWED to state as fact about our own numbers - the chat teaches it, this shows it */}
        <Button size="small" startIcon={<FunctionsIcon sx={{ fontSize: 14 }} />} variant={view === "numbers" ? "contained" : "text"}
          onClick={() => chooseView("numbers")} sx={{ minWidth: 0, fontSize: 11 }}>Numbers</Button>
      </Box>
      {error && <Alert severity="error" sx={{ borderRadius: 0, py: 0 }}>{error}</Alert>}
      {!data?.providers?.length && <Alert severity="info" sx={{ borderRadius: 0, py: 0 }}>Add a CLI agent in Settings to run this work. API providers are optional.</Alert>}
      <input ref={fileRef} hidden type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple onChange={(e) => upload(e.target.files)} />
      {uploading && <Box sx={{ px: 1, py: 0.5, color: FAINT, fontSize: 11 }}>Attaching image…</Box>}
      <Box sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        {view === "numbers" ? (
          <SemanticPanel />
        ) : session && view === "terminal" ? (
          <TerminalPane sid={session.sid} height="100%" />
        ) : session ? (
          <SessionPane sid={session.sid} height="100%">
            <AssistantThread key={`${task.TaskId}-${threadKey}`} task={task} messages={data.messages}
              onAsked={dropAsk} selectionRef={selectionRef}
              attachmentsRef={attachmentsRef} onSent={sent} onClearAttachments={clearAttachments}
              onAttach={() => fileRef.current?.click()} onReport={makeReport} reportBusy={reportBusy} />
          </SessionPane>
        ) : null}
      </Box>
    </Box>
  );
}

export default GeneralWorkspace;
