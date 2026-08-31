// SOUL.md, written from a short interview.
//
// STYLE.md and TRIAGE.md bootstrap themselves from history — the owner's sent mail IS how they
// write. SOUL.md cannot: who you answer for, what an agent may never decide alone, which systems
// are yours, who outranks whom. None of that is in a mailbox. It is in the owner's head, and
// until somebody says it the document is about a stranger called John Smith.
//
// So it asks. Seven questions, none of them required, each one saying why it is being asked —
// a form that explains itself gets answered; a form that does not gets abandoned. The AI writes
// the document from the answers, and it lands in the editor as a first draft the owner owns.
import React, { useEffect, useState } from "react";
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, TextField, Typography,
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import api from "./api";
import { BORDER, DIM, FAINT, INK, PANEL2 } from "./theme.jsx";

export default function SoulInterview({ open, onClose, onWritten }) {
  const [qs, setQs] = useState(null);
  const [ctx, setCtx] = useState({});
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    api.get("/api/soul/interview").then(({ data }) => { setQs(data.questions || []); setCtx(data.context || {}); })
      .catch((e) => setErr(e?.response?.data?.detail || "Could not load the questions"));
  }, [open]);

  const answered = Object.values(answers).filter((v) => String(v || "").trim()).length;
  const write = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/api/soul/interview", { answers });
      onWritten?.(data.doc);
      onClose();
    } catch (e) { setErr(e?.response?.data?.detail || "Could not write it"); }
    setBusy(false);
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        Write SOUL.md from a few questions
        <Typography variant="caption" sx={{ color: FAINT, display: "block", fontWeight: 400, mt: 0.25 }}>
          Answer what you can — every one is optional, and you edit the result like any other document.
          {ctx.channels?.length ? ` It already knows about ${ctx.channels.join(", ")}${ctx.repos?.length ? ` and ${ctx.repos.length} repositor${ctx.repos.length === 1 ? "y" : "ies"}` : ""}.` : ""}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: "8px !important" }}>
        {err && <Alert severity="error" onClose={() => setErr("")}>{err}</Alert>}
        {qs === null ? <CircularProgress size={22} sx={{ m: 3, alignSelf: "center" }} /> : qs.map((q, i) => (
          <Box key={q.key}>
            <Typography sx={{ fontSize: 13.5, fontWeight: 700, color: INK }}>{i + 1}. {q.q}</Typography>
            {/* a form that says why it is asking gets answered */}
            <Typography variant="caption" sx={{ color: FAINT, display: "block", mb: 0.75 }}>{q.why}</Typography>
            <TextField fullWidth multiline minRows={2} maxRows={6} size="small" placeholder={q.placeholder}
              value={answers[q.key] || ""} onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
              sx={{ bgcolor: "#fff", "& textarea": { fontSize: 13 } }} />
          </Box>
        ))}
        {!!ctx.writes_most?.length && (
          <Box sx={{ bgcolor: PANEL2, border: `1px solid ${BORDER}`, borderRadius: 1.5, p: 1.25 }}>
            <Typography variant="caption" sx={{ color: DIM, fontWeight: 700, display: "block" }}>
              Who writes to you most, if it helps answer the people question
            </Typography>
            <Typography variant="caption" sx={{ color: FAINT }}>{ctx.writes_most.slice(0, 6).join(" · ")}</Typography>
          </Box>
        )}
      </DialogContent>
      {busy && <LinearProgress />}
      <DialogActions>
        <Typography variant="caption" sx={{ color: FAINT, flex: 1, pl: 1.5 }}>
          {answered ? `${answered} of ${qs?.length || 7} answered` : "Nothing answered yet"}
        </Typography>
        <Button onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="contained" disableElevation disabled={busy || !answered} onClick={write}
          startIcon={busy ? <CircularProgress size={12} sx={{ color: "#fff" }} /> : <AutoAwesomeIcon sx={{ fontSize: 15 }} />}>
          {busy ? "Writing…" : "Write SOUL.md"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
