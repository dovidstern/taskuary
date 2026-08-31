"""On top of seed_demo.py: an assistant post (with ideas, why, what it reviewed, its note), so the
README's Timeline shot shows the assistant. Run with TASKUARY_HOME pointed at the demo home."""
import json, re
from taskuary import config, assistant
from taskuary.store import SQLiteStore

s = SQLiteStore(config.db_path())
msgs = {m['Subject']: m for m in s.feed(limit=200, days=14)}
mid = lambda sub: next((m['MessageId'] for k, m in msgs.items() if sub.lower() in (k or '').lower()), None)

def llm(system, user, **k):
    keys = re.findall(r'^\[((?:followup|promise|prep|cold):[^\]]+)\]', user, flags=re.M)
    say = []
    if keys:
        say.append({'key': keys[0], 'text': "No word from Dana on the SOW since Tuesday; I'd nudge her today - the board call is Thursday.",
                    'why': 'Your last mail asked for the signed SOW; three days of silence on a Thursday deadline', 'mid': None})
    say += [
        {'key': 'idea:headcount-summit', 'text': "Summit is missing from the headcount query AND the weekly report - one fix, not two; I'd have codex check the site table it reads.",
         'why': 'TQ-0010 "Weekly headcount report misses one site" and the nightly headcount FAILED row name the same site', 'mid': mid('headcount'),
         'task': None},
        {'key': 'idea:csv-export-finance', 'text': "Finance asks for the same numbers by hand every week; the CSV export (TQ-0011) should ship before the Q3 report, not after.",
         'why': 'Sarah Chen: "Finance keeps retyping the numbers" (CSV export) and "the top-10 breakdown before the board call" (Q3 vendor spend) - the same people, the same week',
         'mid': mid('CSV export'), 'task': None},
    ]
    return json.dumps({'say': say, 'notes': 'Checked the SOW thread (silent since Tue), both headcount rows and the finance asks. Nightly headcount FAILED once - '
                       'worth a line only if it fails again tonight. Dark-mode chart bug (mid on file) is with the agent; nothing to add until it reports.'})

out = assistant.run(s, llm=llm, force=True)
print('assistant post:', out.get('said'), 'lines, message', out.get('message_id'))
