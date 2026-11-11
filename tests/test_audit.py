import importlib.util
import json
import os
from pathlib import Path
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1] / 'scripts/audit_repositories.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTest(unittest.TestCase):
    def test_zero_cached_size_with_real_tree_is_not_empty(self):
        repo = dict(name='fresh', fork=False, private=False, description='A tool', topics=['tool'],
                    license={'key': 'mit'}, size=0, default_branch='main', archived=False,
                    html_url='https://github.com/example/fresh', open_issues_count=0, pushed_at='2026-11-11')
        tree = {'tree': [{'path': 'README.md'}, {'path': '.github/workflows/quality.yml'}]}
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(audit, 'gh', side_effect=[[[repo]], tree]), patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}):
                    audit.main()
                report = Path('repository-audit.md').read_text()
                self.assertNotIn('空仓库', report)
                self.assertIn('基础元数据齐全', report)
            finally:
                os.chdir(previous)

    def test_only_explicit_empty_repository_response_is_accepted(self):
        response = CompletedProcess([], 1, json.dumps({'message': 'Git Repository is empty.'}), 'HTTP 409')
        with patch.object(audit.subprocess, 'run', return_value=response):
            self.assertIsNone(audit.gh('api', 'test', allow_empty=True))
        failed = CompletedProcess([], 1, json.dumps({'message': 'Not Found'}), 'HTTP 404')
        with patch.object(audit.subprocess, 'run', return_value=failed):
            with self.assertRaises(RuntimeError):
                audit.gh('api', 'test', allow_empty=True)


if __name__ == '__main__':
    unittest.main()
