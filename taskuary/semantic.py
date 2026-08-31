"""The semantic layer: what a business number MEANS in THIS company's books.

An ERP API answers the question you asked, not the one you meant. Sage Intacct is configured
per company - the chart of accounts, the dimensions, which entries carry rent, whether a
facility is a LOCATION or a DEPARTMENT - so "EBITDAR for Norfolk in July" has no correct
answer that can be derived from the API alone. Ask an AI to write that query and it will
produce something plausible and wrong, every time, and confidently.

So a metric here is not a query. It is a query PLUS the known-good numbers it was proved
against:

    definition   what the owner means by the metric, in words
    spec         how to compute it (object, filters, which field is the value)
    fixtures     (scope, period) -> the number the owner already knows is right
    status       draft until every fixture reconciles; verified only while they all do

`check()` runs the spec against each fixture and compares. A metric becomes `verified` only
when it matches on at least MIN_FIXTURES real facilities - which is the whole point: one
facility matching is a coincidence, three is a definition. It is demoted the moment a fixture
stops reconciling, so a chart-of-accounts change surfaces as a FAILURE and not as a wrong
number in a report nobody re-checked.

A verified metric is then frozen into a Taskuary skill (the same ~/.taskuary/skills folder the
`agent` report type already loads), and named in the assistant's prompt, so every later run
resolves "EBITDAR for Norfolk" through the certified definition instead of re-deriving it.

Nothing here writes to Intacct. Every call is the same read-only readByQuery the reports use,
through the same connector card and the same role gate.
"""
import json, re, time
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from loguru import logger

from . import config

# One facility reconciling is luck; the owner asked for "a few facilities with known numbers".
MIN_FIXTURES = 3
# Money never lands on the cent across systems - a rounding difference is not a wrong definition.
DEFAULT_TOLERANCE = 0.01
AGGREGATES = ('sum', 'count', 'avg', 'min', 'max', 'first')
MAX_ROWS = 20_000        # a facility-month of GL detail, not a year of the whole company
_SLUG = re.compile(r'[^a-z0-9]+')


def slug(name: str) -> str: return _SLUG.sub('-', str(name or '').strip().lower()).strip('-') or 'metric'


# ── periods ────────────────────────────────────────────────────────────────────────────
# What the owner types is "2026-07" or "2026-07-01..2026-07-31". What Intacct wants is
# MM/DD/YYYY - the format the API actually accepts, and the one an AI writing this by hand
# gets wrong first. A spec may say {"date_format": "iso"} when its field is a real date type.
def period_range(period: str) -> tuple:
    """'2026-07' -> (2026-07-01, 2026-07-31); '2026' -> the year; 'a..b' -> exactly that."""
    p = str(period or '').strip()
    if '..' in p:
        a, b = [x.strip() for x in p.split('..', 1)]
        return date.fromisoformat(a), date.fromisoformat(b)
    if re.fullmatch(r'\d{4}', p): return date(int(p), 1, 1), date(int(p), 12, 31)
    if re.fullmatch(r'\d{4}-\d{2}', p):
        y, m = int(p[:4]), int(p[5:7])
        return date(y, m, 1), date(y, m, monthrange(y, m)[1])
    d = date.fromisoformat(p)
    return d, d


def fmt_date(d: date, how: str = 'us') -> str:
    return d.isoformat() if str(how).lower() in ('iso', 'ymd') else d.strftime('%m/%d/%Y')


def substitute(filters, scope: str, period: str, how: str = 'us') -> list:
    """Put the fixture's facility and period into the spec's filters.

    {scope} is whatever names one row of the grain (a LOCATIONID, a DEPARTMENTID, an entity);
    {period_start} and {period_end} are the window. Everything else passes through untouched.
    """
    start, end = period_range(period) if period else (None, None)
    subs = {'{scope}': str(scope or ''),
            '{period}': str(period or ''),
            '{period_start}': fmt_date(start, how) if start else '',
            '{period_end}': fmt_date(end, how) if end else ''}
    def one(v):
        if isinstance(v, (list, tuple)): return [one(x) for x in v]
        s = str(v)
        for k, r in subs.items(): s = s.replace(k, r)
        return s
    return [[f[0], f[1], one(f[2]) if len(f) > 2 else None] for f in (filters or [])]


# ── running one ────────────────────────────────────────────────────────────────────────
def spec_of(metric: dict) -> dict:
    try: return json.loads(metric.get('SpecJson') or '{}')
    except ValueError: raise ValueError(f"metric {metric.get('Name')} has an unreadable spec")


def _aggregate(rows: list, field: str, how: str, sign: float):
    """The rows Intacct returned, reduced to the one number the metric names.

    Intacct returns every field as TEXT, blanks included, so the cast happens here - and a
    blank is skipped rather than counted as zero, because an empty amount column usually means
    the field name is wrong and averaging it to zero would hide exactly that.
    """
    how = str(how or 'sum').lower()
    if how not in AGGREGATES: raise ValueError(f'unknown aggregate {how!r} - use one of {", ".join(AGGREGATES)}')
    if how == 'count': return float(len(rows)) * sign
    if not field: raise ValueError(f'{how} needs a value_field - which column holds the number?')
    vals = []
    for r in rows:
        raw = str(r.get(field, '')).strip().replace(',', '').replace('$', '')
        if not raw: continue
        try: vals.append(float(raw.strip('()')) * (-1 if raw.startswith('(') and raw.endswith(')') else 1))
        except ValueError: continue
    if not vals:
        if not rows: return 0.0
        raise ValueError(f"no numbers in field {field!r} across {len(rows)} rows - is that the right column?")
    out = {'sum': sum(vals), 'avg': sum(vals) / len(vals), 'min': min(vals), 'max': max(vals), 'first': vals[0]}[how]
    return out * sign


def evaluate(store, metric: dict, scope: str = None, period: str = None) -> dict:
    """Compute the metric for one scope and period. Read-only, through the connector card."""
    from .reports import resolve_cfg
    from .intacct import query
    spec = spec_of(metric)
    obj = str(spec.get('object') or '').strip()
    if not obj: raise ValueError('the spec names no Intacct object (GLENTRY, APBILL, GLACCOUNT, ...)')
    value_field = spec.get('value_field')
    fields = spec.get('fields') or ([value_field] if value_field else None)
    filters = substitute(spec.get('filters'), scope, period, spec.get('date_format') or 'us')
    cfg = resolve_cfg(store, {'type': 'intacct', 'connector_id': metric.get('ConnectorId')})
    t0 = time.time()
    rows = query(cfg, obj, fields, filters, limit=int(spec.get('max_rows') or MAX_ROWS))
    value = _aggregate(rows, value_field, spec.get('aggregate') or 'sum', float(spec.get('sign') or 1))
    return {'value': value, 'rows': len(rows), 'ms': int((time.time() - t0) * 1000),
            'object': obj, 'filters': filters, 'scope': scope, 'period': period}


def reconciles(got, expected, tolerance=None) -> bool:
    """Within tolerance. A tolerance below 1 is read as a FRACTION of the expected number, so
    0.005 means "half a percent" on a nine-figure balance and does not have to be restated
    per facility; 1 or more is an absolute amount in dollars."""
    tol = DEFAULT_TOLERANCE if tolerance is None else float(tolerance)
    allow = abs(float(expected)) * tol if 0 < tol < 1 else tol
    return abs(float(got) - float(expected)) <= max(allow, DEFAULT_TOLERANCE)


# ── proving one ────────────────────────────────────────────────────────────────────────
def check(store, mid: int, actor: str = 'owner') -> dict:
    """Run every fixture and record what happened. This is the ONLY road to 'verified'.

    A metric with too few fixtures stays a draft however well it reconciles: the owner's own
    rule is that a definition is not proved until it has matched on a few different facilities.
    """
    m = store.get_metric(mid)
    if not m: raise ValueError(f'no metric {mid}')
    fixtures = store.list_fixtures(mid)
    results, passed = [], 0
    for f in fixtures:
        try:
            got = evaluate(store, m, f.get('Scope'), f.get('Period'))['value']
            ok = reconciles(got, f['Expected'], f.get('Tolerance'))
            store.record_fixture(f['FixtureId'], got, ok, None)
            passed += ok
            results.append({'fixtureId': f['FixtureId'], 'scope': f.get('Scope'), 'period': f.get('Period'),
                            'expected': f['Expected'], 'got': got, 'pass': ok,
                            'off': round(float(got) - float(f['Expected']), 2)})
        except Exception as e:                       # a bad object name, a dead session, a wrong column
            store.record_fixture(f['FixtureId'], None, False, str(e)[:400])
            results.append({'fixtureId': f['FixtureId'], 'scope': f.get('Scope'), 'period': f.get('Period'),
                            'expected': f['Expected'], 'got': None, 'pass': False, 'error': str(e)[:400]})
    enough = len(fixtures) >= MIN_FIXTURES
    ok = bool(fixtures) and passed == len(fixtures) and enough
    note = ('' if ok else
            f'{len(fixtures)} known number(s) - needs {MIN_FIXTURES} before it can be trusted' if not enough
            else f'{len(fixtures) - passed} of {len(fixtures)} did not reconcile')
    status = 'verified' if ok else ('draft' if not enough else 'broken')
    store.update_metric(mid, {'Status': status, 'LastCheckAt': datetime.now().isoformat(sep=' ', timespec='seconds'),
                              'LastCheckPass': 1 if ok else 0, 'LastCheckNote': note}, actor)
    if ok: write_skill(store, store.get_metric(mid), actor)
    store.audit('metric', mid, 'check', actor, detail={'status': status, 'passed': passed, 'of': len(fixtures)})
    return {'metricId': mid, 'name': m['Name'], 'status': status, 'passed': passed, 'of': len(fixtures),
            'note': note, 'results': results}


# ── freezing one ───────────────────────────────────────────────────────────────────────
def skill_md(metric: dict, fixtures: list) -> str:
    """The certified definition as a skill file - the shape reports.py already loads."""
    spec = spec_of(metric)
    lines = [f"# {metric.get('Label') or metric['Name']}", '',
             f"Verified definition of **{metric['Name']}** in this company's Sage Intacct. Use it as written; "
             'do not re-derive the query. It was proved against the known numbers below.', '',
             '## What it means', (metric.get('Definition') or '').strip() or '_(not written)_', '',
             f"One row is: {metric.get('Grain') or 'not stated'}", '',
             '## How it is computed', '```json', json.dumps(spec, indent=2), '```', '',
             'Placeholders: `{scope}` is the facility (or whatever names one row of the grain), '
             '`{period_start}` / `{period_end}` are the window. Run it through Taskuary '
             f'(`POST /api/tools/run` with `{{"type": "metric", "name": "{metric["Name"]}", '
             '"scope": "...", "period": "YYYY-MM"}}`) rather than rebuilding the query.', '']
    if fixtures:
        lines += ['## Proved against', '', '| facility | period | known number | source |', '|---|---|---|---|']
        lines += [f"| {f.get('Scope') or ''} | {f.get('Period') or ''} | {f.get('Expected')} | {f.get('Source') or ''} |"
                  for f in fixtures]
        lines.append('')
    if (metric.get('Notes') or '').strip():
        lines += ['## What was learned proving it', metric['Notes'].strip(), '']
    return '\n'.join(lines)


def write_skill(store, metric: dict, actor: str = 'owner') -> str:
    name = f"intacct-{slug(metric['Name'])}"
    folder = config.home() / 'skills' / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'SKILL.md').write_text(skill_md(metric, store.list_fixtures(metric['MetricId'])), encoding='utf-8')
    if metric.get('Skill') != name: store.update_metric(metric['MetricId'], {'Skill': name}, actor)
    logger.info(f"semantic: wrote skill {name} for verified metric {metric['Name']}")
    return name


def resolve(store, name: str, scope: str = None, period: str = None) -> dict:
    """The certified number, or a refusal that says why. An unverified metric REFUSES rather
    than answering: a plausible wrong number is the failure this whole module exists to stop."""
    m = store.metric_by_name(name)
    if not m: raise ValueError(f'no metric called {name!r} - define it first, then prove it against known numbers')
    if m['Status'] != 'verified':
        raise ValueError(f"metric {m['Name']} is {m['Status']}, not verified"
                         + (f" ({m['LastCheckNote']})" if m.get('LastCheckNote') else '')
                         + ' - it will not answer until its known numbers reconcile')
    out = evaluate(store, m, scope, period)
    return {'metric': m['Name'], 'label': m.get('Label') or m['Name'], **out,
            'definition': m.get('Definition') or '', 'verifiedAt': m.get('LastCheckAt')}


# ── what the assistant is told ─────────────────────────────────────────────────────────
def block(store, budget: int = 2_400) -> str:
    """The paragraph the assistant and the coder context carry: which numbers are certified,
    which are still being proved, and the honest instruction about the ones that are not.

    Without this the model invents a GLENTRY query, gets a plausible figure, and presents it
    with the same confidence as a verified one.
    """
    try: metrics = store.list_metrics()
    except Exception: return ''
    if not metrics: return ''
    good = [m for m in metrics if m['Status'] == 'verified']
    other = [m for m in metrics if m['Status'] != 'verified']
    lines = ['INTACCT SEMANTIC LAYER — this company\'s Intacct is customised, so a query you write '
             'yourself will be plausible and wrong. These definitions were proved against numbers '
             'the owner already knew:']
    for m in good:
        lines.append(f"- {m['Name']}" + (f" ({m['Label']})" if m.get('Label') else '')
                     + f" — {(m.get('Definition') or '').strip()[:200]}"
                     + (f" [one row = {m['Grain']}]" if m.get('Grain') else ''))
    if good:
        lines.append('Get one with POST /api/tools/run {"type": "metric", "name": "<name>", "scope": '
                     '"<facility>", "period": "YYYY-MM"} - it returns the certified number. Do not '
                     'rebuild the query yourself.')
    if other:
        lines.append('NOT yet proved, and they will refuse to answer until they are: '
                     + ', '.join(f"{m['Name']} ({m['Status']})" for m in other) + '.')
    lines.append('For any number NOT listed above: you may explore with {"type": "intacct_fields", '
                 '"object": "..."} and {"type": "intacct", "object": "...", "filters": [...]}, but say '
                 'plainly that the result is unverified, and offer to prove it - the owner gives you a '
                 'few facilities whose numbers they already know, you save them as fixtures, and the '
                 'definition is only trusted once it reconciles on all of them.')
    out = '\n'.join(lines)
    return out if len(out) <= budget else out[:budget] + '…'
