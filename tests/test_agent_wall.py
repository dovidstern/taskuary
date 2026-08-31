"""The wall: what agents tell each other.

peers() and dirty() read facts off git and the run trace - who holds which file, who is busy.
True, and about as expressive as a security camera: they cannot say "the migration is half
applied, don't run the tests yet" or "this is green, safe to build on". Only the agent doing
the work knows that, so it writes it down, and the next agent reads it before it starts.

An agent in a terminal has a shell and no API token, so the door is `taskuary --note` /
`taskuary --board`, with the session telling the child which agent, task and checkout it is.
"""
import json
import os
import unittest
from unittest import mock

from taskuary import blackboard as bb, terminal
from taskuary.store import MemoryStore

CWD = os.path.normcase(os.path.normpath('C:/work/fanapp' if os.name == 'nt' else '/work/fanapp'))


class PostingTests(unittest.TestCase):
    def test_a_note_lands_on_the_checkout_it_was_written_in(self):
        s = MemoryStore()
        n = bb.post(s, 'store.py is mine for the next 20 minutes', 'working', 'codex', CWD, 7)
        self.assertEqual((n['Kind'], n['Agent'], n['TaskId']), ('working', 'codex', 7))
        self.assertEqual(len(bb.wall(s, CWD)), 1)
        self.assertEqual(bb.wall(s, 'C:/work/other'), [])       # another repo is none of its business

    def test_a_note_with_no_words_is_refused(self):
        s = MemoryStore()
        for empty in ('', '   ', None):
            with self.assertRaises(ValueError): bb.post(s, empty)

    def test_only_the_kinds_the_agents_are_taught_are_accepted(self):
        s = MemoryStore()
        for k in bb.KINDS: bb.post(s, 'x', k, 'coder', CWD)
        with self.assertRaises(ValueError): bb.post(s, 'x', 'shipit', 'coder', CWD)

    def test_a_speech_is_trimmed_to_a_line(self):
        s = MemoryStore()
        n = bb.post(s, 'word ' * 800, 'note', 'coder', CWD)
        self.assertLessEqual(len(n['Body']), 1200)
        self.assertNotIn('\n', n['Body'])

    def test_everything_but_the_words_is_optional(self):
        """An agent that knows only what it wants to say still gets to say it."""
        s = MemoryStore()
        n = bb.post(s, 'the mssql tests need pyodbc')
        self.assertEqual((n['Agent'], n['Kind'], n['TaskId']), ('agent', 'note', None))


class ReadingTests(unittest.TestCase):
    def test_the_prompt_gets_a_pointer_and_the_newest_note_not_the_whole_wall(self):
        """A seed is typed into a TUI on one line; the transcript does not belong there."""
        s = MemoryStore()
        for i, (k, body) in enumerate((('working', 'taking auth.py'), ('blocked', 'need the staging key'),
                                       ('ready', 'auth done, suite green'))):
            bb.post(s, body, k, f'agent{i}', CWD)
        text = bb.wall_text(s, CWD)
        self.assertIn('auth done, suite green', text)       # the newest, in full
        self.assertNotIn('taking auth.py', text)            # ...and not the whole history
        self.assertIn('taskuary --board', text)             # with the way to read the rest
        self.assertIn('3 note(s)', text)
        self.assertLess(len(text), 700)                     # it shares a line with the task itself

    def test_an_empty_wall_says_nothing_at_all(self):
        """A prompt paragraph that says "no notes" is tokens spent to say nothing."""
        self.assertEqual(bb.wall_text(MemoryStore(), CWD), '')

    def test_who_has_read_it_is_recorded_once_per_reader(self):
        s = MemoryStore()
        n = bb.post(s, 'watch out for the flaky test', 'note', 'coder', CWD)
        s.mark_note_read(n['NoteId'], 'codex')
        s.mark_note_read(n['NoteId'], 'codex')
        s.mark_note_read(n['NoteId'], 'gemini')
        self.assertEqual(s.get_note(n['NoteId'])['ReadBy'], 'codex,gemini')

    def test_the_etiquette_names_the_command_that_writes_and_the_one_before_a_push(self):
        self.assertIn('taskuary --note', bb.HOW_TO_POST)
        self.assertIn('--kind ready', bb.HOW_TO_POST)


class TheSeedTests(unittest.TestCase):
    def test_a_session_tells_its_cli_which_agent_task_and_checkout_it_is(self):
        env = terminal.session_env('codex', 7, CWD)
        self.assertEqual((env['TASKUARY_AGENT'], env['TASKUARY_TASK'], env['TASKUARY_CWD']), ('codex', '7', CWD))

    def test_a_shell_with_no_task_carries_nothing_it_cannot_answer_for(self):
        self.assertEqual(terminal.session_env('', None, ''), {})

    def test_the_wall_rides_into_the_next_agents_prompt(self):
        s = MemoryStore()
        tid = s.create_task({'Title': 'ship the thing', 'Kind': 'coding'}, 'o')
        bb.post(s, 'the migration is half applied - do not run the tests yet', 'blocked', 'codex', CWD)
        seed = terminal.seed_text(s, tid, repo=None, cwd=CWD)
        self.assertIn('half applied', seed)
        self.assertIn('taskuary --board', seed)

    def test_a_general_task_with_no_checkout_gets_no_wall(self):
        """The wall is per checkout; a question about a meeting has none."""
        s = MemoryStore()
        tid = s.create_task({'Title': 'prep the board meeting', 'Kind': 'general'}, 'o')
        bb.post(s, 'do not touch store.py', 'working', 'codex', CWD)
        seed = terminal.seed_text(s, tid, repo=None, cwd='')
        self.assertNotIn('do not touch store.py', seed)


class TheRulesTests(unittest.TestCase):
    def test_coder_md_tells_the_agent_to_read_it_first_and_post_before_pushing(self):
        from pathlib import Path
        md = (Path(__file__).resolve().parent.parent / 'taskuary' / 'templates' / 'coder.md').read_text(encoding='utf-8')
        self.assertIn('taskuary --board', md)
        self.assertIn('--kind ready', md)
        self.assertIn('Read it first', md)


class TheApiTests(unittest.TestCase):
    def test_the_board_can_read_and_write_the_same_wall(self):
        from fastapi.testclient import TestClient
        from taskuary import server
        c = TestClient(server.app)
        posted = c.post('/api/board/notes', json={'body': 'from the board', 'kind': 'ready'})
        self.assertEqual(posted.status_code, 200)
        got = c.get('/api/board/notes').json()
        self.assertIn('from the board', [n['Body'] for n in got['data']])
        self.assertEqual(got['kinds'], list(bb.KINDS))
        self.assertEqual(c.post('/api/board/notes', json={'body': 'x', 'kind': 'nope'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
