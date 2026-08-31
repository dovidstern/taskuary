"""The installs chart in the README, drawn from PyPI's own numbers.

Two things make a downloads number honest, and pypistats gives one of them:

* **Mirrors are not people.** Every full PyPI mirror pulls every release, so a package with
  three real users can read as hundreds. `mirrors=False` is the public API's own split and
  the series here uses it exclusively.
* **CI is not people either** - and this is the part the public API cannot do. PyPI's raw
  dataset carries an `installer` field (pip, poetry, uv, bandersnatch, "Browser") that would
  separate `pip install` in a GitHub runner from one on somebody's laptop, but it lives in
  BigQuery, not in pypistats. So the chart says "without mirrors" and does not claim to have
  removed CI: a number that overstates itself quietly is worse than one that says what it is.

No matplotlib: the SVG is written out directly, the way docs/learning-loop.svg is, so the
workflow needs one small dependency and the chart stays diffable in review.

    python tools/pypi_downloads.py --package taskuary --history docs/downloads.csv --out docs/downloads.svg
"""
import argparse, csv, json, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://pypistats.org/api/packages'
# pypistats.org rate-limits by user agent and answers 429 to anonymous library traffic from a
# shared address (observed 2026-08-31 from a laptop; a named agent went straight through). So the
# library is the road and a named plain request is the shoulder.
UA = 'taskuary-downloads-chart (+https://github.com/ldbumble/taskuary)'

WIDTH, HEIGHT = 760, 240
PAD_L, PAD_R, PAD_T, PAD_B = 46, 12, 34, 26
DAYS = 180                    # what the pypistats overall endpoint keeps


def _get(pkg: str, what: str, **params) -> dict:
    """One pypistats endpoint, as JSON. pypistats itself where it is installed and answering;
    otherwise the same URL with a user agent that says who is asking."""
    try:
        import pypistats                                # only the workflow needs it installed
        return json.loads(getattr(pypistats, what)(pkg, format='json', **params))
    except Exception as e:
        print(f'pypistats {what} did not answer ({e}); asking the API directly', file=sys.stderr)
        q = f"?{urlencode({k: str(v).lower() for k, v in params.items()})}" if params else ''
        with urlopen(Request(f'{API}/{pkg}/{what}{q}', headers={'User-Agent': UA}), timeout=30) as r:
            return json.load(r)


def series(payload: dict) -> list:
    """[(iso date, downloads)] with mirror traffic dropped, from an overall payload."""
    return [(r['date'], int(r['downloads'])) for r in (payload.get('data') or [])
            if r.get('category') in (None, 'without_mirrors') and r.get('date')]


def fetch(pkg: str) -> list:
    """The last ~180 days as the API keeps them, mirrors excluded."""
    return series(_get(pkg, 'overall', mirrors=False))


def merge(old: list, new: list) -> list:
    """One row per day, newest fetch winning, older days kept once they age out of the window -
    the whole point of committing a CSV rather than re-asking for a 180-day window forever."""
    by = {d: n for d, n in old}
    by.update({d: n for d, n in new})
    return sorted(by.items())


def read_history(path: Path) -> list:
    if not path.exists(): return []
    with path.open(newline='', encoding='utf-8') as f:
        return [(r['date'], int(r['downloads'])) for r in csv.DictReader(f) if r.get('date')]


def write_history(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['date', 'downloads'])
        w.writerows(rows)


def totals(rows: list, today: date = None) -> dict:
    """Day, week and month from the SERIES, so the caption and the bars can never disagree."""
    end = today or (datetime.fromisoformat(rows[-1][0]).date() if rows else date.today())
    by = {d: n for d, n in rows}
    span = lambda days: sum(by.get((end - timedelta(days=i)).isoformat(), 0) for i in range(days))
    return {'last_day': by.get(end.isoformat(), 0), 'last_week': span(7), 'last_month': span(30)}


def _mean7(vals: list) -> list:
    return [round(sum(vals[max(0, i - 6):i + 1]) / len(vals[max(0, i - 6):i + 1]), 2) for i in range(len(vals))]


def _nice(top: int) -> int:
    """A round y-axis ceiling: 1, 2, 5 x 10^n, so the gridline reads as a number."""
    if top <= 5: return 5
    step = 10 ** (len(str(int(top))) - 1)
    for m in (1, 2, 5, 10):
        if top <= m * step: return m * step
    return 10 * step


def svg(rows: list, pkg: str, window: int = DAYS) -> str:
    """A bar per day with a 7-day mean over it. Colours are mid-tones that read on GitHub's
    light and dark themes, and the text follows the reader's theme through a media query -
    an <img> SVG carries its own rendering context, so that actually works here."""
    rows = rows[-window:]
    n = len(rows)
    t = totals(rows)
    plot_w, plot_h = WIDTH - PAD_L - PAD_R, HEIGHT - PAD_T - PAD_B
    top = _nice(max([v for _, v in rows] or [0]))
    x = lambda i: PAD_L + (plot_w * (i + 0.5) / n if n else 0)
    y = lambda v: PAD_T + plot_h - (plot_h * min(v, top) / top)
    bw = max(1.0, (plot_w / n) * 0.72) if n else 1.0
    bars = ''.join(
        f'<rect x="{x(i) - bw / 2:.2f}" y="{y(v):.2f}" width="{bw:.2f}" '
        f'height="{max(0.0, PAD_T + plot_h - y(v)):.2f}" class="bar"/>'
        for i, (_, v) in enumerate(rows) if v)
    mean = _mean7([v for _, v in rows])
    line = ' '.join(f'{x(i):.2f},{y(v):.2f}' for i, v in enumerate(mean))
    caption = (f'{t["last_day"]:,} today · {t["last_week"]:,} this week · {t["last_month"]:,} this month'
               if n else 'no downloads reported yet')
    first, last = (rows[0][0], rows[-1][0]) if n else ('', '')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"
     role="img" aria-label="Daily {pkg} downloads from PyPI, mirrors excluded: {caption}">
  <style>
    .ink {{ fill: #24292f; font: 600 12px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }}
    .dim {{ fill: #6e7781; font: 400 10.5px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }}
    .bar {{ fill: #55697a; }}
    .mean {{ fill: none; stroke: #b3542f; stroke-width: 1.6; stroke-linejoin: round; }}
    .grid {{ stroke: #d0d7de; stroke-width: 1; }}
    @media (prefers-color-scheme: dark) {{
      .ink {{ fill: #e6edf3; }} .dim {{ fill: #9198a1; }}
      .bar {{ fill: #7d97ab; }} .grid {{ stroke: #30363d; }} .mean {{ stroke: #e08a5c; }}
    }}
  </style>
  <text x="{PAD_L}" y="15" class="ink">{pkg} · installs from PyPI, mirrors excluded</text>
  <text x="{PAD_L}" y="28" class="dim">{caption}</text>
  <line x1="{PAD_L}" y1="{y(top):.2f}" x2="{WIDTH - PAD_R}" y2="{y(top):.2f}" class="grid"/>
  <line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{WIDTH - PAD_R}" y2="{PAD_T + plot_h}" class="grid"/>
  <text x="{PAD_L - 6}" y="{y(top) + 4:.2f}" class="dim" text-anchor="end">{top:,}</text>
  <text x="{PAD_L - 6}" y="{PAD_T + plot_h + 4}" class="dim" text-anchor="end">0</text>
  {bars}
  <polyline points="{line}" class="mean"/>
  <text x="{PAD_L}" y="{HEIGHT - 8}" class="dim">{first}</text>
  <text x="{WIDTH - PAD_R}" y="{HEIGHT - 8}" class="dim" text-anchor="end">{last} · 7-day mean in orange</text>
</svg>
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', default='taskuary')
    ap.add_argument('--history', default='docs/downloads.csv')
    ap.add_argument('--out', default='docs/downloads.svg')
    ap.add_argument('--from-json', help='a saved pypistats overall payload, instead of the network')
    ap.add_argument('--strict', action='store_true', help='fail on a fetch error instead of leaving the chart alone')
    a = ap.parse_args(argv)
    hist = Path(a.history)
    if a.from_json:
        new = series(json.loads(Path(a.from_json).read_text(encoding='utf-8')))
    else:
        try:
            new = fetch(a.package)
        except Exception as e:
            # a package with no downloads yet, or pypistats having a bad day, is not a reason to
            # paint the repository's checks red
            print(f'could not read pypistats for {a.package}: {e}', file=sys.stderr)
            return 1 if a.strict else 0
    rows = merge(read_history(hist), new)
    if not rows:
        print('nothing to chart yet'); return 0
    write_history(hist, rows)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg(rows, a.package), encoding='utf-8')
    t = totals(rows)
    print(f'{len(rows)} days · {t["last_day"]} today · {t["last_week"]} this week · {t["last_month"]} this month')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
