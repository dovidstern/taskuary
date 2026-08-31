"""The semantic layer: a number is only trusted once it has reconciled with numbers the owner
already knew. These tests are about the RULE, not about Intacct - `evaluate` is stubbed, because
the point being protected is "an unproved definition refuses to answer", which has nothing to do
with the network.
"""
import json
from datetime import date

import pytest

from taskuary import semantic
from taskuary.store import MemoryStore


@pytest.fixture
def st(): return MemoryStore()


SPEC = {'object': 'GLENTRY', 'value_field': 'AMOUNT', 'aggregate': 'sum',
        'filters': [['LOCATIONID', '=', '{scope}'],
                    ['BATCH_DATE', '>=', '{period_start}'], ['BATCH_DATE', '<=', '{period_end}']]}


def define(st, **over) -> int:
    return st.save_metric({'Name': 'ebitdar', 'Label': 'EBITDAR', 'Grain': 'facility-month',
                           'Definition': 'earnings before interest, tax, depreciation, amortisation and rent',
                           'SpecJson': json.dumps({**SPEC, **over})}, 'owner')


def answers(monkeypatch, by_scope: dict):
    """Stub the ERP: each facility returns whatever this dict says, no network, no credentials."""
    monkeypatch.setattr(semantic, 'evaluate',
                        lambda store, m, scope=None, period=None: {'value': by_scope[scope], 'rows': 1, 'ms': 0,
                                                                   'object': 'GLENTRY', 'filters': [],
                                                                   'scope': scope, 'period': period})


# ── periods: what the owner types vs what Intacct wants ────────────────────────────────
def test_month_becomes_its_first_and_last_day():
    assert semantic.period_range('2026-07') == (date(2026, 7, 1), date(2026, 7, 31))
    assert semantic.period_range('2026-02') == (date(2026, 2, 1), date(2026, 2, 28))


def test_year_and_explicit_window():
    assert semantic.period_range('2026') == (date(2026, 1, 1), date(2026, 12, 31))
    assert semantic.period_range('2026-07-04..2026-07-06') == (date(2026, 7, 4), date(2026, 7, 6))


def test_intacct_gets_us_dates_unless_the_spec_says_iso():
    """The format the API actually accepts, and the one a hand-written query gets wrong first."""
    assert semantic.fmt_date(date(2026, 7, 1)) == '07/01/2026'
    assert semantic.fmt_date(date(2026, 7, 1), 'iso') == '2026-07-01'


def test_placeholders_are_filled_from_the_fixture():
    out = semantic.substitute(SPEC['filters'], 'NORFOLK', '2026-07')
    assert out == [['LOCATIONID', '=', 'NORFOLK'],
                   ['BATCH_DATE', '>=', '07/01/2026'], ['BATCH_DATE', '<=', '07/31/2026']]


# ── the aggregate: Intacct returns every column as text ────────────────────────────────
def test_amounts_arrive_as_text_and_are_still_summed():
    rows = [{'AMOUNT': '1,200.50'}, {'AMOUNT': '$300'}, {'AMOUNT': '(100)'}]
    assert semantic._aggregate(rows, 'AMOUNT', 'sum', 1) == pytest.approx(1400.50)


def test_a_wrong_column_is_an_error_not_a_zero():
    """Averaging an empty column to 0.00 would hide the actual mistake, which is the column name."""
    with pytest.raises(ValueError, match='right column'):
        semantic._aggregate([{'AMOUNT': '5'}], 'AMONUT', 'sum', 1)


def test_no_rows_at_all_is_a_real_zero():
    assert semantic._aggregate([], 'AMOUNT', 'sum', 1) == 0.0


def test_sign_flips_the_credit_convention():
    assert semantic._aggregate([{'AMOUNT': '100'}], 'AMOUNT', 'sum', -1) == -100


# ── tolerance ──────────────────────────────────────────────────────────────────────────
def test_a_fraction_is_a_percentage_and_a_whole_number_is_dollars():
    assert semantic.reconciles(100_500, 100_000, 0.01)          # within 1%
    assert not semantic.reconciles(102_000, 100_000, 0.01)
    assert semantic.reconciles(100_040, 100_000, 50)            # within $50
    assert not semantic.reconciles(100_060, 100_000, 50)


def test_cents_never_fail_a_definition():
    assert semantic.reconciles(1_000_000.004, 1_000_000)


# ── the rule the whole module exists for ───────────────────────────────────────────────
def test_one_matching_facility_is_not_a_proof(st, monkeypatch):
    """The owner's own rule: one facility matching is luck, a few is a definition."""
    mid = define(st)
    st.add_fixture(mid, {'Scope': 'NORFOLK', 'Period': '2026-07', 'Expected': 900.0}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0})
    r = semantic.check(st, mid)
    assert r['passed'] == 1 and r['status'] == 'draft'
    assert 'needs 3' in r['note']


def test_three_reconciling_facilities_certify_it(st, monkeypatch, tmp_path):
    mid = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(mid, {'Scope': s, 'Period': '2026-07', 'Expected': v}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0})
    r = semantic.check(st, mid)
    assert r['status'] == 'verified' and r['passed'] == 3
    assert st.get_metric(mid)['Skill'] == 'intacct-ebitdar'


def test_one_facility_drifting_demotes_the_whole_metric(st, monkeypatch):
    """A chart-of-accounts change must surface as a failure, not as a wrong number in a report."""
    mid = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(mid, {'Scope': s, 'Period': '2026-07', 'Expected': v}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0})
    assert semantic.check(st, mid)['status'] == 'verified'
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 700.0})
    r = semantic.check(st, mid)
    assert r['status'] == 'broken' and '1 of 3 did not reconcile' in r['note']
    assert [x['off'] for x in r['results'] if not x['pass']] == [250.0]


def test_an_unverified_metric_refuses_to_answer(st, monkeypatch):
    """The failure this module exists to stop: a plausible number stated as if it were proved."""
    mid = define(st)
    answers(monkeypatch, {'NORFOLK': 900.0})
    with pytest.raises(ValueError, match='not verified'):
        semantic.resolve(st, 'ebitdar', 'NORFOLK', '2026-07')


def test_an_unknown_metric_says_so(st):
    with pytest.raises(ValueError, match='define it first'):
        semantic.resolve(st, 'nonesuch', 'NORFOLK', '2026-07')


def test_a_verified_metric_answers(st, monkeypatch):
    mid = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(mid, {'Scope': s, 'Period': '2026-07', 'Expected': v}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0, 'WOODLANDS': 610.0})
    semantic.check(st, mid)
    assert semantic.resolve(st, 'ebitdar', 'WOODLANDS', '2026-07')['value'] == 610.0


def test_editing_the_spec_un_verifies_it(st, monkeypatch):
    """The proof was of the OLD query. Nothing has proved the new one."""
    from taskuary import server
    mid = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(mid, {'Scope': s, 'Period': '2026-07', 'Expected': v}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0})
    semantic.check(st, mid)
    assert st.get_metric(mid)['Status'] == 'verified'
    monkeypatch.setattr(server, 'store', st)
    server.metric_save(server.MetricBody(Name='ebitdar', Spec={**SPEC, 'sign': -1}))
    assert st.get_metric(mid)['Status'] == 'draft'


# ── what the assistant is told ─────────────────────────────────────────────────────────
def test_nothing_defined_says_nothing(st):
    assert semantic.block(st) == ''


def test_the_block_separates_proved_from_unproved(st, monkeypatch):
    good = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(good, {'Scope': s, 'Period': '2026-07', 'Expected': v}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0})
    semantic.check(st, good)
    st.save_metric({'Name': 'occupancy', 'SpecJson': json.dumps(SPEC)}, 'owner')
    text = semantic.block(st)
    assert 'ebitdar' in text and 'occupancy (draft)' in text
    assert 'unverified' in text and 'refuse to answer' in text


def test_the_skill_file_carries_the_definition_and_its_proof(st, monkeypatch):
    mid = define(st)
    for s, v in (('NORFOLK', 900.0), ('PARHAM', 1200.0), ('CHERRYDALE', 450.0)):
        st.add_fixture(mid, {'Scope': s, 'Period': '2026-07', 'Expected': v, 'Source': 'the monthly package'}, 'owner')
    answers(monkeypatch, {'NORFOLK': 900.0, 'PARHAM': 1200.0, 'CHERRYDALE': 450.0})
    semantic.check(st, mid)
    from taskuary import config
    md = (config.home() / 'skills' / 'intacct-ebitdar' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'facility-month' in md and 'NORFOLK' in md and 'the monthly package' in md
    assert '"object": "GLENTRY"' in md


# ── the HTTP surface the chat actually drives ──────────────────────────────────────────
def test_the_whole_loop_over_the_api(monkeypatch, tmp_path):
    """Define, try, give it known numbers, prove it - the exact sequence the assistant is told
    to walk the owner through, over the endpoints it is told to call."""
    from fastapi.testclient import TestClient
    from taskuary import server
    c = TestClient(server.app)
    monkeypatch.setattr(semantic, 'evaluate',
                        lambda store, m, scope=None, period=None: {'value': {'A': 10.0, 'B': 20.0, 'C': 30.0}[scope],
                                                                   'rows': 1, 'ms': 1, 'object': 'GLENTRY',
                                                                   'filters': [], 'scope': scope, 'period': period})
    m = c.post('/api/semantic/metrics', json={'Name': 'apitest', 'Label': 'API test', 'Grain': 'facility-month',
                                              'Definition': 'a number', 'Spec': SPEC}).json()
    mid = m['MetricId']
    assert m['Status'] == 'draft'
    assert c.post(f'/api/semantic/metrics/{mid}/try', json={'scope': 'A', 'period': '2026-07'}).json()['value'] == 10.0
    for s, v in (('A', 10.0), ('B', 20.0), ('C', 30.0)):
        c.post(f'/api/semantic/metrics/{mid}/fixtures', json={'Scope': s, 'Period': '2026-07', 'Expected': v})
    r = c.post(f'/api/semantic/metrics/{mid}/check').json()
    assert r['status'] == 'verified' and r['passed'] == 3
    listed = next(x for x in c.get('/api/semantic/metrics').json()['data'] if x['MetricId'] == mid)
    assert listed['Status'] == 'verified' and len(listed['fixtures']) == 3
    c.delete(f'/api/semantic/metrics/{mid}')
    assert not any(x['MetricId'] == mid for x in c.get('/api/semantic/metrics').json()['data'])


def test_the_metric_tool_refuses_an_unproved_number(monkeypatch):
    """POST /api/tools/run is the road the assistant is given; it must not hand back a guess."""
    from taskuary.reports import REGISTRY
    st = MemoryStore()
    st.save_metric({'Name': 'unproved', 'SpecJson': json.dumps(SPEC)}, 'owner')
    with pytest.raises(ValueError, match='not verified'):
        REGISTRY['metric']({'store': st, 'name': 'unproved', 'scope': 'A', 'period': '2026-07'})
