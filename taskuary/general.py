"""Taskuary's general-work agent and its two views.

A general session uses either an already-authenticated CLI agent or an optional API connector and
owns a small, persistent conversation on the task.  The object implements the same
live-session surface as ``terminal.Term`` so assistant-ui and xterm are only renderers: queueing,
attachments, the Wall, browser association, and session lifetime all point at one session id.
"""
import base64, json, mimetypes, re, threading, time, uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from loguru import logger

from . import llm as llm_mod


USER_TYPE = 'assistant_user'
ASSISTANT_TYPE = 'assistant_agent'
GENERAL_KINDS = {'general', 'research', 'marketing', 'triage'}
SCROLLBACK = 200_000
MAX_CONTEXT = 24_000
MAX_REPLY_TOKENS = 2_000
REPORT_DRAFT_TOKENS = 1_200
REPORT_SKILL_CHARS = 2_400
_IMAGE_PATH = re.compile(r'(?P<path>(?:[A-Za-z]:\\|/)[^\r\n<>|"?*]+?\.(?:png|jpe?g|gif|webp))', re.I)

REPORT_DRAFT_SYSTEM = """You turn a completed assistant conversation into a REUSABLE scheduled-report instruction.
Return ONLY JSON: {"title":"short recurring report title","prompt":"standalone instruction"}.
The prompt must reproduce the useful work on every future run using CURRENT information. Preserve the goal,
sources or systems to inspect, important search/query steps, comparison criteria, caveats, provenance requirements,
and the desired report sections or output shape. Convert one-off dates into relative windows when appropriate.
Never copy secrets, access tokens, incidental debugging, old findings, or the previous answer as if it were current.
Do not mention this conversation. Do not add a schedule; the user chooses that separately."""


def handles(task: dict | None) -> bool:
    """Kinds that belong to the conversational agent rather than a coding or reply workflow."""
    return str((task or {}).get('Kind') or 'general').lower() in GENERAL_KINDS


def provider_options(store) -> list:
    """Every configured CLI login first, then optional API/local-model connectors."""
    out = []
    from .clis import KNOWN
    labels = {k['cmd']: k['label'] for k in KNOWN}
    for row in store.list_agents():
        try: cfg = json.loads(row.get('Config') or '{}')
        except ValueError: cfg = {}
        cmd = re.split(r'[\\/]', str(cfg.get('cmd') or row['Name']))[-1].lower().rsplit('.', 1)[0]
        label = labels.get(cmd) or cmd or row['Name']
        if row['Name'] != cmd: label += f" · {row['Name']}"
        out.append({'id': f"cli:{row['Name']}", 'pick': f"cli:{row['Name']}", 'type': 'cli',
                    'label': f'{label} (your CLI)', 'model': cfg.get('model') or ''})
    for row in store.list_connectors():
        if row.get('Type') not in llm_mod.AI_TYPES or not row.get('Active'): continue
        if not row.get('HasSecret') and row.get('Type') != 'ollama': continue
        try: cfg = json.loads(row.get('ConfigJson') or '{}')
        except ValueError: cfg = {}
        model = cfg.get('model') or cfg.get('deployment') or ''
        out.append({'id': f"connector:{row['ConnectorId']}", 'connector_id': row['ConnectorId'],
                    'pick': f"connector:{row['ConnectorId']}", 'type': row['Type'],
                    'label': f"{row.get('Name') or row['Type']} (API)", 'model': model})
    return out


def _selected(store, connector_id=None, model=None, pick=None) -> tuple[str, str, str]:
    options = provider_options(store)
    wanted = str(pick or (f'connector:{connector_id}' if connector_id else '')
                 or store.get_settings().get('assistant_ai') or '')
    if wanted and ':' not in wanted and wanted.isdigit(): wanted = f'connector:{wanted}'
    if not wanted: wanted = f"cli:{store.get_settings().get('default_agent') or 'coder'}"
    choice = next((o for o in options if o['pick'] == wanted), None) or (options[0] if options else None)
    if not choice: return '', '', model or ''
    return choice['pick'], choice['label'], model or choice['model']


def chat_rows(store, tid: int) -> list:
    return [c for c in store.list_comments(tid) if c.get('ActorType') in (USER_TYPE, ASSISTANT_TYPE)]


def history(store, tid: int) -> list:
    return [{'id': f"comment-{c['CommentId']}",
             'role': 'assistant' if c.get('ActorType') == ASSISTANT_TYPE else 'user',
             'content': [{'type': 'text', 'text': c.get('Body') or ''}],
             'createdAt': c.get('CreatedAt')} for c in chat_rows(store, tid)]


def _cut(text, n):
    text = str(text or '')
    return text if len(text) <= n else text[:n] + f'\n[trimmed {len(text) - n:,} characters]'


def _prompt(store, tid: int) -> tuple[str, str]:
    detail = store.task_detail(tid) or {}
    task = detail.get('task') or {}
    soul = _cut(store.doc('soul') or '', 4_000)
    counsel = _cut(store.doc('counsel') or '', 3_000)
    system = (
        "You are the Taskuary general-work assistant. Help complete research, planning, writing, "
        "marketing, operational, and other non-coding work. The task and source material below are "
        "authoritative. Be direct and useful. Never claim you searched the web, opened a system, sent "
        "something, or changed a record unless a tool actually did it. Ask when a necessary fact is "
        "missing. Do not turn this into a coding task or instruct a coding CLI.\n\n"
        f"OPERATOR RULES\n{_cut(soul, 4_000)}\n\nASSISTANT STYLE\n{_cut(counsel, 3_000)}"
    )
    sources = []
    for m in (detail.get('messages') or [])[-12:]:
        who = m.get('FromName') or m.get('FromEmail') or m.get('SourceName') or m.get('Channel') or 'source'
        sources.append(f"FROM {who} ({m.get('SentAt') or ''})\n{_cut(m.get('BodyText'), 3_000)}")
    turns = []
    for c in chat_rows(store, tid)[-30:]:
        role = 'ASSISTANT' if c.get('ActorType') == ASSISTANT_TYPE else 'USER'
        turns.append(f"{role}: {_cut(c.get('Body'), 4_000)}")
    user = (f"TASK {detail.get('ref') or tid}\nTITLE: {task.get('Title') or ''}\n"
            f"SUMMARY: {task.get('Summary') or ''}\nSTATUS: {task.get('Status') or ''}\n\n"
            + ("SOURCE MATERIAL\n" + '\n\n'.join(sources) + '\n\n' if sources else '')
            + "CONVERSATION\n" + '\n\n'.join(turns)
            + "\n\nRespond to the last USER turn. Do not repeat the task context.")
    return system, _cut(user, MAX_CONTEXT)


def _fallback_report_draft(store, tid: int) -> dict:
    """A useful editable draft even when the selected brain is unavailable or returns prose."""
    detail = store.task_detail(tid) or {}
    task = detail.get('task') or {}
    asks = [str(c.get('Body') or '').strip() for c in chat_rows(store, tid)
            if c.get('ActorType') == USER_TYPE and str(c.get('Body') or '').strip()]
    title = str(task.get('Title') or 'Recurring assistant report').strip()[:100]
    prompt = ('Repeat this work using current information at every run. Verify claims with the available tools, '
              'include dates and source links, distinguish confirmed facts from unknowns, and end with the practical '
              'changes or follow-ups that matter now.')
    if asks:
        prompt += '\n\nThe original requests to preserve:\n' + '\n'.join(f'- {_cut(a, 1800)}' for a in asks[-8:])
    return {'title': title, 'prompt': prompt[:12000]}


def report_draft(store, tid: int, pick=None, model=None) -> dict:
    """Condense a task conversation into the prompt of an ``agent`` report.

    This is deliberately a separate model call: it neither adds a chat turn nor reruns the work.
    The deterministic fallback remains editable, so a formatting failure cannot block scheduling.
    """
    task = store.get_task(tid)
    if not task: raise ValueError(f'no task {tid}')
    if not handles(task): raise ValueError('only assistant discussions can become recurring reports here')
    rows = chat_rows(store, tid)
    if not any(c.get('ActorType') == ASSISTANT_TYPE for c in rows):
        raise ValueError('finish at least one assistant exchange before turning it into a report')
    fallback = _fallback_report_draft(store, tid)
    chosen, _provider, chosen_model = _selected(store, model=model, pick=pick)
    try:
        brain = llm_mod.build_llm(store, pick=chosen or None, model=chosen_model or None)
    except Exception as e:
        logger.warning(f'assistant report draft could not select a model for task {tid}: {e}')
        return fallback
    if not brain: return fallback
    conversation = '\n\n'.join(
        f"{'ASSISTANT' if c.get('ActorType') == ASSISTANT_TYPE else 'USER'}: {_cut(c.get('Body'), 3500)}"
        for c in rows[-24:])
    user = (f"TASK TITLE: {task.get('Title') or ''}\nTASK SUMMARY: {task.get('Summary') or ''}\n\n"
            f"CONVERSATION\n{_cut(conversation, 20000)}")
    try:
        raw = str(brain(REPORT_DRAFT_SYSTEM, user, max_tokens=REPORT_DRAFT_TOKENS) or '').strip()
        clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I)
        try: made = json.loads(clean)
        except (ValueError, TypeError):
            block = re.search(r'\{.*\}', clean, flags=re.S)
            made = json.loads(block.group(0)) if block else {}
        title, prompt = str(made.get('title') or '').strip(), str(made.get('prompt') or '').strip()
        if not prompt: return fallback
        return {'title': (title or fallback['title'])[:100], 'prompt': prompt[:12000]}
    except Exception as e:
        logger.warning(f'assistant report draft fell back for task {tid}: {e}')
        return fallback


def save_report_skill(tid: int, title: str, prompt: str) -> str:
    """Persist a long generated workflow as a Taskuary-owned, provider-neutral skill.

    ``reports.run_agent`` expands this file into the CLI prompt, so the same recurring skill
    works with Claude, Codex, Gemini, or another configured CLI instead of being installed into
    one provider's private skill directory.
    """
    from . import config
    slug = re.sub(r'[^a-z0-9]+', '-', str(title or '').lower()).strip('-')[:52] or 'recurring-report'
    slug = f'{slug}-tq-{tid}'
    folder = config.home() / 'skills' / slug
    folder.mkdir(parents=True, exist_ok=True)
    text = (f'---\nname: {slug}\ndescription: Reusable workflow promoted from Taskuary task {tid}.\n---\n\n'
            f'# {title.strip()}\n\n{prompt.strip()}\n')
    (folder / 'SKILL.md').write_text(text, encoding='utf-8')
    return slug


def _images(paths) -> list:
    out = []
    for raw in paths or []:
        try:
            p = Path(str(raw)).resolve()
            ct = mimetypes.guess_type(str(p))[0] or ''
            if ct not in llm_mod.VISION_TYPES or not p.is_file() or p.stat().st_size > llm_mod.VISION_BYTES: continue
            out.append((ct, base64.b64encode(p.read_bytes()).decode()))
        except OSError: continue
        if len(out) >= llm_mod.VISION_MAX: break
    return out


class GeneralSession:
    """A connector-backed conversation with the live-session contract used by the terminal."""
    mode = 'assistant'
    argv = []
    cwd = ''
    label = 'Taskuary assistant'
    agent = 'assistant'
    cli = 'taskuary'

    def __init__(self, store, task_id: int, connector_id=None, model=None, pick=None):
        self.sid = uuid.uuid4().hex[:12]
        self.store, self.task_id = store, task_id
        self.pick, self.provider, self.model = _selected(store, connector_id, model, pick)
        self.started = datetime.now().isoformat(sep=' ', timespec='seconds')
        self.buf, self.n, self.ended, self.last = deque(), 0, None, time.time()
        self.subs, self.taps = [], []
        self.alive, self.busy = True, False
        self.rows, self.cols = 32, 110
        self._input, self._lock = '', threading.Lock()
        from .witness import Witness
        self.witness = Witness()
        self._restore_terminal()

    def _append(self, text):
        if not text: return
        self.buf.append(text); self.n += len(text)
        while self.n > SCROLLBACK and len(self.buf) > 1: self.n -= len(self.buf.popleft())

    def _emit(self, text):
        self._append(text)
        for loop, q in list(self.subs):
            try: loop.call_soon_threadsafe(q.put_nowait, text)
            except RuntimeError: pass
        for fn in list(self.taps):
            try: fn(text)
            except Exception as e: logger.debug(f'assistant session tap failed: {e}')

    def _restore_terminal(self):
        title = (self.store.get_task(self.task_id) or {}).get('Title') or f'Task {self.task_id}'
        self._append(f'\x1b[1;36mTaskuary assistant\x1b[0m  {self.provider or "no AI connector"} {self.model}\r\n'
                     f'\x1b[2m{title}\x1b[0m\r\n\r\n')
        for row in chat_rows(self.store, self.task_id):
            if row.get('ActorType') == USER_TYPE:
                self._append(f'\x1b[1;34myou>\x1b[0m {row.get("Body") or ""}\r\n')
            else:
                self._append(f'\x1b[1;32massistant>\x1b[0m {row.get("Body") or ""}\r\n\r\n')
        self._append('\x1b[1;34myou>\x1b[0m ')

    def subscribe(self, loop, q): self.subs.append((loop, q))
    def unsubscribe(self, q): self.subs = [(loop, item) for loop, item in self.subs if item is not q]
    def tap(self, fn): self.taps.append(fn)
    def untap(self, fn): self.taps = [item for item in self.taps if item is not fn]
    def scrollback(self): return ''.join(self.buf)
    def resize(self, rows, cols): self.rows, self.cols = int(rows), int(cols)
    def idle(self): return round(time.time() - self.last, 1)
    def files(self): return []
    def phase(self): return 'working' if self.busy else 'parked'
    def waiting(self): return self.alive and not self.busy
    def tail(self, n=3):
        from .terminal import plain
        return [line for line in plain(self.scrollback()[-8000:]).splitlines() if line.strip()][-n:]

    def write(self, data):
        """Make xterm a second composer for the same conversation."""
        if not self.alive: return
        for ch in str(data or ''):
            if ch in ('\r', '\n'):
                prompt, self._input = self._input.strip(), ''
                if prompt and not self.busy:
                    self._emit('\r\n')
                    threading.Thread(target=self.send_prompt, args=(prompt,), kwargs={'echo': False}, daemon=True).start()
                continue
            if ch in ('\x08', '\x7f'):
                if self._input:
                    self._input = self._input[:-1]; self._emit('\b \b')
                continue
            if ch == '\x03':
                self._emit('^C\r\n\x1b[1;34myou>\x1b[0m '); self._input = ''
                continue
            if ch >= ' ':
                self._input += ch; self._emit(ch)

    def send_prompt(self, text: str, attachments=None, connector_id=None, model=None, echo=True,
                    pick=None, trace=None, cancel=None) -> str:
        text = str(text or '').strip()
        if not text: raise ValueError('empty message')
        if not self.alive: raise RuntimeError('assistant session has ended')
        if not self._lock.acquire(blocking=False): raise RuntimeError('the assistant is already working')
        self.busy, self.last = True, time.time()
        try:
            if connector_id is not None or model or pick:
                self.pick, self.provider, self.model = _selected(self.store, connector_id, model, pick)
            if not self.pick:
                raise RuntimeError('connect a CLI agent or an AI provider before starting general work')
            if echo: self._emit(f'\x1b[1;34myou>\x1b[0m {text}\r\n')
            self.store.add_comment(self.task_id, 'owner', USER_TYPE, text)
            system, user = _prompt(self.store, self.task_id)
            paths = list(attachments or []) + [m.group('path') for m in _IMAGE_PATH.finditer(text)]
            if paths and self.pick.startswith('cli:'):
                user += '\n\nATTACHED FILES (read these when relevant)\n' + '\n'.join(str(Path(p).resolve()) for p in paths)
            def visible(kind, name, detail):
                if trace: trace(kind, name, detail)
                if kind == 'tool_call':
                    target = next(iter((detail.get('args') or {}).values()), '') if isinstance(detail, dict) else ''
                    self._emit(f'\x1b[33mtool>\x1b[0m {name} {str(target)[:180]}\r\n')
                elif kind == 'tool_result' and isinstance(detail, dict) and detail.get('is_error'):
                    self._emit(f'\x1b[31mtool error>\x1b[0m {str(detail.get("result") or "")[:240]}\r\n')
            brain = llm_mod.build_llm(self.store, pick=self.pick, model=self.model or None,
                                      trace=visible, cancel=cancel)
            if not brain: raise RuntimeError('the selected AI connector is unavailable')
            reply = str(brain(system, user, max_tokens=MAX_REPLY_TOKENS, images=_images(paths)) or '').strip()
            if not reply: raise RuntimeError('the model returned an empty response')
            self.store.add_comment(self.task_id, 'assistant', ASSISTANT_TYPE, reply)
            self.store.audit('task', self.task_id, 'assistant_reply', 'assistant', 'agent',
                             {'provider': self.provider, 'model': self.model, 'chars': len(reply)})
            self._emit(f'\x1b[1;32massistant>\x1b[0m {reply}\r\n\r\n')
            return reply
        except Exception as e:
            self._emit(f'\x1b[1;31merror>\x1b[0m {e}\r\n\r\n')
            raise
        finally:
            self.busy, self.last = False, time.time()
            self._emit('\x1b[1;34myou>\x1b[0m ')
            self._lock.release()

    def close(self):
        self.alive, self.ended = False, time.time()
        self._emit('\r\n\x1b[2msession closed\x1b[0m\r\n')
        for loop, q in list(self.subs):
            try: loop.call_soon_threadsafe(q.put_nowait, None)
            except RuntimeError: pass

    def info(self, tail=0):
        from . import browserview
        return {'sid': self.sid, 'label': self.label, 'cwd': '', 'taskId': self.task_id,
                'agent': self.agent, 'cli': 'taskuary', 'mode': self.mode, 'alive': self.alive,
                'started': self.started, 'idle': self.idle(), 'phase': self.phase(),
                'waiting': self.waiting(), 'cmd': f'{self.provider or "AI connector"} {self.model}'.strip(),
                'provider': self.provider, 'pick': self.pick,
                'connector_id': int(self.pick.split(':', 1)[1]) if self.pick.startswith('connector:') else None,
                'model': self.model, 'files': [],
                'browser': browserview.state(self.sid), 'work': None,
                **({'tail': self.tail(tail)} if tail else {})}


def session_for(tid: int):
    from . import terminal
    return next((s for s in list(terminal.SESSIONS.values())
                 if s.task_id == tid and s.alive and getattr(s, 'mode', '') == 'assistant'), None)


def start_session(store, tid: int, connector_id=None, model=None, actor='owner', pick=None) -> GeneralSession:
    from . import terminal
    task = store.get_task(tid)
    if not task: raise ValueError(f'no task {tid}')
    if not handles(task): raise ValueError('assistant view is for general, research, marketing, and triage tasks')
    existing = session_for(tid)
    if existing:
        if connector_id is not None or model or pick:
            existing.pick, existing.provider, existing.model = _selected(store, connector_id, model, pick)
        return existing
    other = next((s for s in list(terminal.SESSIONS.values()) if s.task_id == tid and s.alive), None)
    if other: raise ValueError('this task already has a different live session')
    session = GeneralSession(store, tid, connector_id, model, pick)
    terminal.SESSIONS[session.sid] = session
    if task.get('Status') == 'open': store.update_task(tid, {'Status': 'in_progress'}, actor)
    return session
