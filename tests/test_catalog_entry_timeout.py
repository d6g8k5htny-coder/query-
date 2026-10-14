"""Git timeout refusal controls; only the Git subprocess boundary is injected."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from universal_law_query import catalog_entry as helper


class CatalogEntryTimeoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.payload = Path(temporary.name) / 'candidate.txt'
        self.payload.write_bytes(b'candidate\n')
        self.argv = [
            '--file', str(self.payload), '--repository', 'Math-',
            '--path', 'frontiers/candidate.txt', '--key', 'candidate',
            '--scope', 'synthetic test only',
        ]

    def assert_lookup_call(self, run):
        run.assert_called_once_with(
            ['git', '-C', str(self.payload.parent), 'log', '-1',
             '--format=%H', '--', self.payload.name],
            capture_output=True, text=True, timeout=10, check=False,
            env=helper._git_env(),
        )

    def test_timeout_becomes_helper_error_with_original_cause(self):
        # Partial output, including an apparently valid commit, is never used.
        for output in (None, b'', b'a' * 40 + b'\n', 'b' * 40 + '\n'):
            with self.subTest(output=output):
                original = subprocess.TimeoutExpired(
                    ['git', 'synthetic-command'], 10,
                    output=output, stderr=b'synthetic-stderr',
                )
                with patch.object(helper.subprocess, 'run', side_effect=original) as run:
                    with self.assertRaises(Exception) as caught:
                        helper.resolve_commit(self.payload, None)
                self.assertIsInstance(caught.exception, helper.HelperError)
                self.assertEqual(str(caught.exception), 'git commit lookup timed out')
                self.assertIs(caught.exception.__cause__, original)
                self.assert_lookup_call(run)

    def test_main_refuses_timeout_without_stub_or_traceback(self):
        original = subprocess.TimeoutExpired(
            ['git', 'synthetic-command'], 10,
            output=b'a' * 40 + b'\n', stderr=b'synthetic-stderr',
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(helper.subprocess, 'run', side_effect=original) as run:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    status = helper.main(self.argv)
                except Exception as error:
                    self.fail('timeout escaped CLI: ' + type(error).__name__)
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), 'REFUSED: git commit lookup timed out\n')
        self.assert_lookup_call(run)
        self.assertEqual(self.payload.read_bytes(), b'candidate\n')

    def test_wrapper_process_returns_refusal_exit(self):
        # Execute the unchanged wrapper as __main__ in a real child process.
        # No slow Git command is launched: the child's Git call alone times out.
        code = '''import runpy, subprocess, sys
from pathlib import Path
from unittest.mock import patch
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'src'))
from universal_law_query import catalog_entry as helper
sys.argv = [str(root / 'catalog_entry_helper.py'), *sys.argv[2:]]
error = subprocess.TimeoutExpired(['git', 'synthetic-command'], 10,
    output=b'a' * 40 + b'\\n', stderr=b'synthetic-stderr')
with patch.object(helper.subprocess, 'run', side_effect=error):
    runpy.run_path(str(root / 'catalog_entry_helper.py'), run_name='__main__')
'''
        flags = ['-B', '-S'] + ['-O'] * sys.flags.optimize
        result = subprocess.run(
            [sys.executable, *flags, '-c', code, str(ROOT), *self.argv],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'REFUSED: git commit lookup timed out\n')

    def test_explicit_commit_bypasses_git_and_preserves_stub(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(helper.subprocess, 'run') as run:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = helper.main([*self.argv, '--commit', 'a' * 40])
        self.assertEqual(status, 0)
        run.assert_not_called()
        self.assertEqual(stderr.getvalue(), '')
        entry = json.loads(stdout.getvalue())
        self.assertEqual(entry['commit'], 'a' * 40)
        self.assertEqual(entry['bytes'], 10)
        self.assertEqual(entry['sha256'], hashlib.sha256(b'candidate\n').hexdigest())
        self.assertIs(entry['catalog_is_not_acceptance'], True)
        self.assertEqual(entry['visibility'], 'public')

    def test_successful_git_lookup_preserves_command_and_budget(self):
        result = subprocess.CompletedProcess(['git'], 0, stdout='c' * 40 + '\n', stderr='')
        with patch.object(helper.subprocess, 'run', return_value=result) as run:
            self.assertEqual(helper.resolve_commit(self.payload, None), 'c' * 40)
        self.assert_lookup_call(run)

    def test_nonzero_or_invalid_git_output_still_refuses(self):
        for status, output in ((1, 'a' * 40), (0, ''), (0, 'main'), (0, 'A' * 40)):
            with self.subTest(status=status, output=output):
                result = subprocess.CompletedProcess(['git'], status, stdout=output, stderr='')
                with patch.object(helper.subprocess, 'run', return_value=result) as run:
                    with self.assertRaisesRegex(helper.HelperError, 'exact commit required'):
                        helper.resolve_commit(self.payload, None)
                self.assert_lookup_call(run)

    def test_os_error_still_preserves_cause(self):
        original = OSError('synthetic missing Git')
        with patch.object(helper.subprocess, 'run', side_effect=original) as run:
            with self.assertRaises(helper.HelperError) as caught:
                helper.resolve_commit(self.payload, None)
        self.assertEqual(str(caught.exception), 'git commit lookup failed: synthetic missing Git')
        self.assertIs(caught.exception.__cause__, original)
        self.assert_lookup_call(run)

    def test_unrelated_error_and_interrupt_are_not_relabelled(self):
        for original in (RuntimeError('synthetic bug'), KeyboardInterrupt()):
            with self.subTest(kind=type(original).__name__):
                with patch.object(helper.subprocess, 'run', side_effect=original) as run:
                    with self.assertRaises(type(original)) as caught:
                        helper.resolve_commit(self.payload, None)
                self.assertIs(caught.exception, original)
                self.assert_lookup_call(run)


if __name__ == '__main__':
    unittest.main()
