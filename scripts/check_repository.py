#!/usr/bin/env python3
"""Offline repository hygiene checks; never prints matching secret values."""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


def check(root):
    root = Path(root).resolve()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    errors = []
    required = ['README.md', 'LICENSE']
    for name in required:
        if not (root / name).is_file() or not (root / name).read_text().strip():
            errors.append(f'{name}: missing or empty')
    secret_patterns = [
        re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}'),
        re.compile(r'github_pat_[A-Za-z0-9_]{50,}'),
        re.compile(r'AKIA[0-9A-Z]{16}'),
        re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    ]
    for name in filter(None, tracked):
        path = root / name
        if not path.exists():
            errors.append(f'{name}: tracked file missing from working tree')
            continue
        if path.is_symlink():
            errors.append(f'{name}: symlink requires manual review; not supported by this starter')
            continue
        if path.name == '.DS_Store' or '.idea' in path.parts or path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            errors.append(f'{name}: local-only file tracked')
        if path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in secret_patterns):
            errors.append(f'{name}: possible credential detected (value withheld)')
        if path.suffix == '.svg':
            try:
                ET.fromstring(content)
            except ET.ParseError:
                errors.append(f'{name}: invalid SVG XML')
        if path.suffix.lower() != '.md':
            continue
        # Avoid examples inside fenced code blocks. Inline relative links only.
        prose = re.sub(r'^```.*?^```\s*$', '', content, flags=re.S | re.M)
        links = re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', prose)
        links += re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)', prose, re.I)
        for link in links:
            link = link.strip('<>')
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (root / unquote(url.path).lstrip('/')) if url.path.startswith('/') else (path.parent / unquote(url.path))
            if not target.resolve().is_relative_to(root):
                errors.append(f'{name}: relative link escapes repository')
            elif not target.exists():
                errors.append(f'{name}: missing local target {url.path}')
    return errors


if __name__ == '__main__':
    root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
    errors = check(root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        sys.exit(1)
    print('Repository hygiene checks passed. Add project-specific tests separately.')
