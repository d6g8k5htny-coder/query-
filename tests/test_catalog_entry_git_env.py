"""Repository-selection controls for the catalog helper; real Git unless stated."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from universal_law_query import catalog_entry as helper

# Independent expectation, matching the existing source builder's routing policy.
REPOSITORY_ENV = {
    'GIT_DIR', 'GIT_WORK_TREE', 'GIT_IMPLICIT_WORK_TREE', 'GIT_COMMON_DIR',
    'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_REPLACE_REF_BASE', 'GIT_GRAFT_FILE', 'GIT_SHALLOW_FILE', 'GIT_PREFIX',
}


class CatalogEntryGitEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # Isolate fixture construction; production behavior is exercised below
        # with explicit routing variables reintroduced into the helper's caller.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('GIT_', 'PYTHON'))}
        self.env.update({
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_AUTHOR_NAME': 'Fixture', 'GIT_COMMITTER_NAME': 'Fixture',
            'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
            'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
            'GIT_AUTHOR_DATE': '2000-01-01T00:00:00Z',
            'GIT_COMMITTER_DATE': '2000-01-01T00:00:00Z',
        })
        self.selected = self.root / 'selected'
        self.foreign = self.root / 'foreign'
        for repo, content in ((self.selected, b'selected source\n'),
                              (self.foreign, b'foreign content\n')):
            repo.mkdir()
            self.git(repo, 'init', '-q')
            (repo / 'target.txt').write_bytes(content)
            if repo == self.foreign:
                (repo / 'untracked.txt').write_bytes(b'foreign decoy\n')
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-qm', 'fixture target')
        self.last_touch = self.git(self.selected, 'rev-parse', 'HEAD').strip()
        self.foreign_commit = self.git(self.foreign, 'rev-parse', 'HEAD').strip()
        (self.selected / 'unrelated.txt').write_bytes(b'unrelated change\n')
        self.git(self.selected, 'add', 'unrelated.txt')
        self.git(self.selected, 'commit', '-qm', 'unrelated later commit')
        self.assertNotEqual(self.git(self.selected, 'rev-parse', 'HEAD').strip(),
                            self.last_touch)
        self.assertNotEqual(self.foreign_commit, self.last_touch)

    def git(self, repo, *args):
        result = subprocess.run(
            ['git', '--no-replace-objects', '-C', str(repo),
             '-c', 'core.hooksPath=' + os.devnull, '-c', 'commit.gpgsign=false',
             *args], env=self.env, capture_output=True, text=True,
            timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def inventory(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def wrapper(self, injected, name='target.txt', commit=None):
        argv = [sys.executable, '-B', '-S', *(['-O'] * sys.flags.optimize),
                str(ROOT / 'catalog_entry_helper.py'),
                '--file', str(self.selected / name), '--repository', 'query-',
                '--path', name, '--key', 'fixture', '--scope', 'synthetic test only']
        if commit is not None:
            argv += ['--commit', commit]
        before = self.inventory()
        result = subprocess.run(argv, cwd=self.root, env={**self.env, **injected},
                                capture_output=True, text=True, timeout=10,
                                check=False)
        self.assertEqual(self.inventory(), before, 'helper modified fixture bytes')
        return result

    def assert_local_entry(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        row = json.loads(result.stdout)
        self.assertEqual(row['commit'], self.last_touch)
        self.assertEqual(row['sha256'], hashlib.sha256(b'selected source\n').hexdigest())
        self.assertEqual(row['bytes'], len(b'selected source\n'))
        self.assertEqual(row['path'], 'target.txt')
        self.assertIs(row['catalog_is_not_acceptance'], True)
        self.assertIn('candidate', row['meaning'])

    def test_ordinary_lookup_keeps_valid_older_last_touch(self):
        self.assert_local_entry(self.wrapper({}))

    def test_wrapper_ignores_foreign_git_directory(self):
        for worktree in (None, self.selected, self.foreign):
            with self.subTest(worktree=str(worktree)):
                injected = {'GIT_DIR': str(self.foreign / '.git')}
                if worktree is not None:
                    injected['GIT_WORK_TREE'] = str(worktree)
                self.assert_local_entry(self.wrapper(injected))

    def test_invalid_routing_paths_do_not_override_selected_repository(self):
        for name in ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY'):
            with self.subTest(variable=name):
                self.assert_local_entry(self.wrapper({name: str(self.root / 'missing')}))

    def test_direct_api_keeps_caller_environment_and_repository_bytes(self):
        environment = {**self.env, 'GIT_DIR': str(self.foreign / '.git'),
                       'GIT_WORK_TREE': str(self.foreign)}
        before = self.inventory()
        with patch.dict(os.environ, environment, clear=True):
            caller = dict(os.environ)
            result = helper.resolve_commit(self.selected / 'target.txt', None)
            self.assertEqual(dict(os.environ), caller)
        self.assertEqual(self.inventory(), before)
        self.assertEqual(result, self.last_touch)

    def test_subprocess_gets_filtered_copy_with_unrelated_values_preserved(self):
        # A mock is used only to inspect the child environment and command.
        environment = {name: 'routing-' + name for name in REPOSITORY_ENV}
        kept = {
            'PATH': '/fixture/bin', 'HOME': '/fixture/home', 'EMPTY': '',
            'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'safe.directory',
            'GIT_CONFIG_VALUE_0': str(self.selected),
            'GIT_CONFIG': '/fixture/config',
            'GIT_CONFIG_PARAMETERS': "'color.ui'='false'",
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_NO_REPLACE_OBJECTS': '1',
            'GIT_LITERAL_PATHSPECS': '1', 'UNRELATED': 'preserved',
        }
        environment.update(kept)
        completed = subprocess.CompletedProcess(['git'], 0, 'a' * 40 + '\n', '')
        with patch.dict(os.environ, environment, clear=True):
            caller = dict(os.environ)
            with patch.object(helper.subprocess, 'run', return_value=completed) as run:
                self.assertEqual(helper.resolve_commit(self.selected / 'target.txt', None),
                                 'a' * 40)
            self.assertEqual(dict(os.environ), caller)
            run.assert_called_once()
            argv, = run.call_args.args
            self.assertEqual(argv, ['git', '-C', str(self.selected), 'log', '-1',
                                    '--format=%H', '--', 'target.txt'])
            expected = dict(capture_output=True, text=True, timeout=10,
                            check=False, env=kept)
            self.assertEqual(run.call_args.kwargs, expected)
            self.assertIsNot(run.call_args.kwargs['env'], os.environ)
            run.call_args.kwargs['env']['UNRELATED'] = 'child-only change'
            self.assertEqual(dict(os.environ), caller)

    def test_untracked_local_name_cannot_borrow_foreign_history(self):
        (self.selected / 'untracked.txt').write_bytes(b'local untracked\n')
        result = self.wrapper({'GIT_DIR': str(self.foreign / '.git')},
                              name='untracked.txt')
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stdout, '')
        self.assertIn('REFUSED: exact commit required', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_explicit_commit_bypass_is_unchanged_under_bad_environment(self):
        bad = {name: str(self.root / 'missing') for name in REPOSITORY_ENV}
        result = self.wrapper(bad, commit='b' * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['commit'], 'b' * 40)
        with patch.dict(os.environ, bad, clear=True):
            before = dict(os.environ)
            with patch.object(helper.subprocess, 'run') as run:
                self.assertEqual(helper.resolve_commit(self.selected / 'target.txt',
                                                       'b' * 40), 'b' * 40)
                run.assert_not_called()
            self.assertEqual(dict(os.environ), before)


if __name__ == '__main__':
    unittest.main()
