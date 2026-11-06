#!/usr/bin/env python3
"""Check that okwow-capture never uploads the secrets planted in a session.

Runs `upload --dry-run` on a Claude Code and a Codex session planted with
API keys, tokens, passwords, credentials in a URL and `.env` output, and fails
if any planted value appears in what would be sent. Nothing leaves the
machine. Run: python3 tests/check_redaction.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURE = ROOT / "plugins" / "okwow" / "scripts" / "okwow-capture"
FIXTURES = ROOT / "tests" / "fixtures"
REPO = "/tmp/okwow-capture-check/repo"
# Fixture tokens carry an invisible separator so secret scanners skip them; it is removed before use.
SEPARATOR = "\u2063"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").replace(SEPARATOR, "")


def main() -> int:
    secrets = json.loads(fixture("planted-secrets.json"))
    with tempfile.TemporaryDirectory() as home:
        Path(REPO).mkdir(parents=True, exist_ok=True)
        Path(home, "capture.json").write_text(
            json.dumps({"repos": {os.path.realpath(REPO): {"space": "space:check", "space_label": "check"}}})
        )
        env = {**os.environ, "OKWOW_CAPTURE_HOME": home, "OKWOW_CAPTURE_STATE": home}
        failed = False
        for harness, name in (("claude", "planted-secrets.jsonl"), ("codex", "planted-secrets-codex.jsonl")):
            session = Path(home, name)
            session.write_text(fixture(name), encoding="utf-8")
            sent = subprocess.run(
                [sys.executable, str(CAPTURE), "upload", "--dry-run", "--harness", harness, str(session)],
                capture_output=True, text=True, env=env, check=True,
            ).stdout
            leaks = sorted(name for name, value in secrets.items() if value in sent)
            if leaks:
                print(f"FAIL {harness}: {len(leaks)} planted secrets would be uploaded: {', '.join(leaks)}")
                failed = True
            elif "[REDACTED" not in sent:
                print(f"FAIL {harness}: the dry run sent nothing to check")
                failed = True
            else:
                print(f"PASS {harness}: none of {len(secrets)} planted secrets would be uploaded")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
