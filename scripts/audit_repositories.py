#!/usr/bin/env python3
"""Read public metadata only and produce a maintenance report; never changes repositories."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import urllib.parse


def gh(*args, allow_empty=False):
    result = subprocess.run(['gh', *args], text=True, capture_output=True)
    if result.returncode:
        try:
            error = json.loads(result.stdout)
        except json.JSONDecodeError:
            error = {}
        if allow_empty and error.get('message', '').lower().rstrip('.') == 'git repository is empty':
            return None
        raise RuntimeError(f'GitHub read failed: {result.stderr.strip()}')
    return json.loads(result.stdout)


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    owner = os.environ.get('AUDIT_OWNER', 'shanghe000')
    # Public endpoint deliberately avoids private account metadata even with a broader local login.
    pages = gh('api', f'users/{owner}/repos?type=owner&per_page=100', '--paginate', '--slurp')
    repositories = [r for page in pages for r in page if not r['fork'] and not r['private']]
    rows = []
    report = ['# 公开原创仓库维护清单', '', f'生成时间：{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}', '',
              '仅包含公开、非 Fork 仓库；不自动创建 Issue、归档或修改设置。未结事项包含 Issue 与 PR。', '',
              '| 仓库 | 状态 | 未结事项 | 最近推送 | 建议跟进 |', '| --- | --- | ---: | --- | --- |']
    for repo in sorted(repositories, key=lambda r: r['name'].lower()):
        missing = []
        if not repo.get('description'):
            missing.append('补简介')
        if not repo.get('topics'):
            missing.append('补主题')
        if not repo.get('license'):
            missing.append('确定许可证')
        # Repository size is cached and can remain zero after the initial push.
        branch = urllib.parse.quote(repo['default_branch'], safe='')
        tree = gh('api', f"repos/{owner}/{repo['name']}/git/trees/{branch}?recursive=1", allow_empty=True)
        if tree is None:
            missing.append('空仓库：补最小内容或决定用途')
        else:
            paths = [entry['path'] for entry in tree['tree']]
            if tree.get('truncated'):
                missing.append('目录过大：以下缺项需人工确认')
            if not any(p.lower() in ['readme.md', 'readme.rst', 'readme.txt', 'readme'] for p in paths):
                missing.append('补 README')
            if not any(p.startswith('.github/workflows/') and p.endswith(('.yml', '.yaml')) for p in paths):
                missing.append('评估是否需要自动检查')
        status = '已归档' if repo['archived'] else '活跃仓库'
        suggestion = '；'.join(missing) or '基础元数据齐全；继续检查实际可用性'
        rows.append(f"| [{cell(repo['name'])}]({repo['html_url']}) | {status} | {repo['open_issues_count']} | {(repo.get('pushed_at') or '-')[:10]} | {suggestion} |")
    report += rows + ['', '许可证、仓库可见性、重命名与归档由维护者单独决策。此报告不检查私有仓库，不代表代码安全或功能审计。', '']
    text = '\n'.join(report)
    Path('repository-audit.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(text)
    print(f'Created report for {len(repositories)} public original repositories.')


if __name__ == '__main__':
    main()
