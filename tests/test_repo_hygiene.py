"""Repository hygiene: no secrets and no personal data files in anything git tracks.

Checks file CONTENTS, not just names. A failure message names the file and line but never prints the match.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SECRET_PATTERNS = {
    "Garmin API key": r"GCDC_[A-Za-z0-9._+/=-]{8,}",
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "GitHub fine-grained token": r"github_pat_[A-Za-z0-9_]{20,}",
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{10,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
FORBIDDEN_NAME = re.compile(r"(^|/)\.env(\.|$)(?!example$)|\.sqlite$|^\.venv/|(^|/)__pycache__/")
ALLOWED_PLACEHOLDER_DIRS = ("secrets/", "data/", "logs/")


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return [f for f in result.stdout.decode().split("\0") if f]


def test_env_example_lists_variable_names_only():
    for n, line in enumerate((ROOT / ".env.example").read_text().splitlines(), 1):
        if line.strip() and not line.startswith("#"):
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*=", line), f".env.example line {n} has a value; names only"


def test_no_secret_patterns_in_tracked_files():
    found = []
    for name in tracked_files():
        path = ROOT / name
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(lines, 1):
            for label, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, line):
                    found.append(f"{name}:{n} looks like a {label}")
    assert not found, "Secrets in tracked files (revoke them, then remove them from history):\n" + "\n".join(found)


def test_no_private_or_generated_files_are_tracked():
    bad = []
    for name in tracked_files():
        if FORBIDDEN_NAME.search(name):
            bad.append(name)
        elif name.startswith(ALLOWED_PLACEHOLDER_DIRS) and Path(name).name != ".gitkeep":
            bad.append(name)
    assert not bad, f"Tracked files that must stay local: {bad}"
