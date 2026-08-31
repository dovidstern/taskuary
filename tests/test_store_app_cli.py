"""A CLI Windows will not let us start.

`where codex` finds it, typing `codex` runs it, and a background run answers "Access is denied."
and nothing else - the Microsoft Store copy. CreateProcess is refused inside the package folder,
and the execution alias only runs for the account the package is registered to.

Reported on an owner's machine (2026-08-31) as `codex exit 1: Access is denied.`, which reads as
an account or billing problem with OpenAI and is nothing of the kind: the CLI never ran. Three
things follow from that: an ordinary install is preferred over the Store copy wherever both
exist, the failure explains itself, and the setup wizard says so before a scheduled run does.
"""
import os
import unittest
from unittest import mock

from taskuary import agents, clis


class NamingTheStoreCopyTests(unittest.TestCase):
    def test_a_package_path_is_the_store_copy_whatever_its_case(self):
        self.assertTrue(clis.store_app(r'C:\Program Files\WindowsApps\OpenAI.Codex_1.0_x64\codex.EXE'))
        self.assertTrue(clis.store_app(r'c:\users\me\appdata\local\microsoft\windowsapps\codex.exe'))

    def test_an_ordinary_install_is_not(self):
        self.assertFalse(clis.store_app(r'C:\Users\me\AppData\Local\Programs\OpenAI\Codex\bin\codex.EXE'))
        self.assertFalse(clis.store_app('/usr/local/bin/codex'))
        self.assertFalse(clis.store_app(''))

    def test_nothing_on_path_is_not_reported_as_blocked(self):
        with mock.patch.object(agents, '_resolve_cmd', side_effect=FileNotFoundError('nope')):
            self.assertEqual(clis.runnable('codex'), ('', False))


class SayingWhatHappenedTests(unittest.TestCase):
    def test_the_message_denies_the_two_wrong_conclusions_and_names_the_cause(self):
        said = agents.denied_msg('codex', r'C:\Program Files\WindowsApps\x\codex.EXE', 'Access is denied.')
        self.assertIn('never ran', said)
        self.assertIn('not a sign-in or billing problem', said)
        self.assertIn('Microsoft Store', said)
        self.assertIn('where codex', said)          # the one command that shows which copy is found

    def test_a_refusal_to_start_is_told_apart_from_a_run_that_failed(self):
        self.assertTrue(agents._DENIED.search('Access is denied.'))
        self.assertTrue(agents._DENIED.search('[WinError 5] Access is denied'))
        self.assertTrue(agents._DENIED.search('bash: /x: Permission denied'))
        self.assertFalse(agents._DENIED.search('the model refused to answer'))


class PickingWhichCopyRunsTests(unittest.TestCase):
    """_resolve_cmd is Windows-only in effect, so the platform is faked - CI is Linux too."""
    def _resolve(self, which, programs_copy, name='codex'):
        with mock.patch.object(agents.os, 'name', 'nt'), \
             mock.patch.object(agents.shutil, 'which', return_value=which), \
             mock.patch.object(agents, '_programs_copy', return_value=programs_copy):
            return agents._resolve_cmd(name)

    def test_an_ordinary_install_beats_the_store_package(self):
        real = r'C:\Users\me\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe'
        self.assertEqual(self._resolve(r'C:\Program Files\WindowsApps\pkg\codex.EXE', real), [real])

    def test_an_ordinary_install_beats_the_execution_alias_too(self):
        """The alias is the copy that answers "Access is denied." when the package is not
        registered for this account, so a real executable is preferred over it as well."""
        real = r'C:\Users\me\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe'
        alias = r'C:\Users\me\AppData\Local\Microsoft\WindowsApps\codex.exe'
        self.assertEqual(self._resolve(alias, real), [real])

    def test_with_no_ordinary_install_the_alias_is_still_used(self):
        """Unchanged behaviour: on the machines where the alias works, it works."""
        alias = r'C:\Users\me\AppData\Local\Microsoft\WindowsApps\codex.exe'
        self.assertEqual(self._resolve(alias, ''), [alias])

    def test_a_package_path_with_nothing_better_falls_back_to_the_shell(self):
        with mock.patch.object(agents.os.path, 'exists', return_value=False):
            got = self._resolve(r'C:\Program Files\WindowsApps\pkg\codex.EXE', '')
        self.assertEqual(got, ['cmd', '/c', 'codex'])

    def test_an_ordinary_path_is_left_exactly_as_found(self):
        real = r'C:\Users\me\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe'
        self.assertEqual(self._resolve(real, ''), [real])


class FindingTheOrdinaryCopyTests(unittest.TestCase):
    def test_it_walks_the_per_user_programs_folder(self):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        binn = root / 'Programs' / 'OpenAI' / 'Codex' / 'bin'
        binn.mkdir(parents=True)
        (binn / 'codex.exe').write_text('x', encoding='utf-8')
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': str(root)}):
            self.assertEqual(agents._programs_copy('codex.EXE'), str(binn / 'codex.exe'))

    def test_a_missing_folder_is_simply_nothing_found(self):
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': os.path.join('no', 'such', 'place')}):
            self.assertEqual(agents._programs_copy('codex.exe'), '')


if __name__ == '__main__':
    unittest.main()
