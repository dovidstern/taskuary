"""A report that only speaks up when something is wrong.

Delivery sends every run, which is useless for "tell me when the nightly job did not run":
a message that arrives whether or not anything is wrong is a message you stop reading. These
tests are about the RULE - no network, no channels - because a rule that misfires at 3am, or
stays silent when it should not, is the whole failure mode.
"""
import pytest

from taskuary import reports


def cfg(**alert): return {'title': 'Nightly job check', 'alert': {'to': '4477…', 'channel': 'whatsapp', **alert}}


# ── counting what came back ────────────────────────────────────────────────────────────
def test_the_row_executors_say_the_count_in_their_headline():
    assert reports.result_count('0 rows', '') == 0
    assert reports.result_count('12 rows', 'a\nb') == 12
    assert reports.result_count('1,204 rows (capped at the default 200)', '') == 1204


def test_prose_results_are_counted_by_their_lines():
    assert reports.result_count('what the assistant would read', 'one\n\ntwo\n') == 2
    assert reports.result_count('', '') == 0


# ── the rule the owner actually asked for ──────────────────────────────────────────────
def test_no_run_in_the_window_speaks_up():
    """The ask: query the run log for the last two hours; if nothing is there, tell me."""
    assert reports.alert_fires(cfg(when='nothing_came_back'), '0 rows', '') == 'nothing came back'


def test_a_run_in_the_window_stays_silent():
    assert reports.alert_fires(cfg(when='nothing_came_back'), '3 rows', '{"job": "ok"}') == ''


def test_the_reason_is_carried_so_the_phone_says_which_rule_tripped():
    why = reports.alert_fires(cfg(when='fewer_than', count=5), '2 rows', 'a\nb')
    assert why == 'only 2 came back, expected at least 5'


# ── the other conditions ───────────────────────────────────────────────────────────────
def test_something_came_back_is_the_inverse():
    assert reports.alert_fires(cfg(when='something_came_back'), '4 rows', 'x') == '4 came back'
    assert reports.alert_fires(cfg(when='something_came_back'), '0 rows', '') == ''


def test_more_than_fires_only_above_the_line():
    assert reports.alert_fires(cfg(when='more_than', count=10), '11 rows', '') != ''
    assert reports.alert_fires(cfg(when='more_than', count=10), '10 rows', '') == ''


def test_contains_and_missing_read_the_headline_and_the_body():
    hit = cfg(when='contains', text='ERROR')
    assert reports.alert_fires(hit, '3 rows', 'all fine\nan Error happened') != ''      # case-insensitive
    assert reports.alert_fires(hit, '3 rows', 'all fine') == ''
    gone = cfg(when='missing', text='completed')
    assert reports.alert_fires(gone, '1 rows', 'still running') != ''
    assert reports.alert_fires(gone, '1 rows', 'completed at 04:00') == ''


# ── the failure cases, which are where an alarm earns its keep ─────────────────────────
def test_a_failed_run_is_never_silently_treated_as_zero():
    """"No rows" from a query that never ran is not the same fact as "no rows" from one that
    did - reporting the second when it was the first would send the owner hunting the wrong thing."""
    why = reports.alert_fires(cfg(when='nothing_came_back'), '', 'Report error: login timeout', failed=True)
    assert 'failed to run' in why and 'could not be judged' in why


def test_watching_for_failure_alone_ignores_healthy_runs():
    assert reports.alert_fires(cfg(when='failed'), '0 rows', '') == ''
    assert reports.alert_fires(cfg(when='failed'), '', 'boom', failed=True) == 'the report failed to run'


def test_an_alert_with_nowhere_to_go_never_fires():
    """Switched on and never filled in - a rule that can only fail at 3am."""
    assert reports.alert_fires({'alert': {'when': 'nothing_came_back', 'to': ''}}, '0 rows', '') == ''


def test_no_alert_configured_is_silence_not_an_error():
    assert reports.alert_fires({}, '0 rows', '') == ''


def test_a_nonsense_condition_is_loud_rather_than_quietly_never_firing():
    with pytest.raises(ValueError, match='unknown alert condition'):
        reports.alert_fires(cfg(when='when_it_feels_wrong'), '0 rows', '')
