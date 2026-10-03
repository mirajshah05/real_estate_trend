"""Scan reachable Git blobs and publishable files without printing secret values.

Run from any directory with Python 3.11+. This is a focused credential check,
not a replacement for a dedicated secret scanner or a penetration test.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    "private_key": rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "github_token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b",
    "aws_access_key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "slack_token": rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b",
    "openai_key": rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b",
    "credential_url": rb"https?://[^\s/:]+:[^\s/@]+@",
}
COMPILED = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def configured_secrets() -> dict[str, bytes]:
    secrets = {}
    for path in (ROOT / ".env", ROOT / "web/.env"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            key, sep, value = line.strip().removeprefix("export ").partition("=")
            if not sep or key.startswith(("#", "VITE_")):
                continue  # Vite's basemap key is intentionally browser-visible.
            if not re.search(r"KEY|TOKEN|SECRET|PASSWORD", key, re.IGNORECASE):
                continue
            value = value.strip().strip("\"'")
            if len(value) >= 8:
                secrets[key] = value.encode()
    return secrets


def main() -> int:
    secrets = configured_secrets()
    findings = []

    def scan(label: str, content: bytes) -> None:
        for name, pattern in COMPILED.items():
            if pattern.search(content):
                findings.append({"location": label, "kind": name})
        for key, value in secrets.items():
            if value in content:
                findings.append({"location": label, "kind": f"configured:{key}"})

    objects = git("rev-list", "--objects", "--all").splitlines()
    blobs = 0
    for row in objects:
        oid = row.split(b" ", 1)[0].decode()
        if git("cat-file", "-t", oid).strip() == b"blob":
            blobs += 1
            scan(f"git:{oid}", git("cat-file", "blob", oid))

    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    worktree_files = 0
    for name in files:
        if not name:
            continue
        path = ROOT / name.decode()
        if path.is_file():
            worktree_files += 1
            scan(str(path.relative_to(ROOT)), path.read_bytes())

    # The generated bundle may contain the public map key, but no backend key.
    bundles = 0
    for path in (ROOT / "web/dist").rglob("*"):
        if path.is_file():
            bundles += 1
            scan(str(path.relative_to(ROOT)), path.read_bytes())

    print(
        json.dumps(
            {
                "reachable_commits": int(git("rev-list", "--count", "--all")),
                "git_blobs": blobs,
                "publishable_files": worktree_files,
                "bundle_files": bundles,
                "configured_backend_secrets_checked": len(secrets),
                "findings": findings,
            },
            indent=2,
        )
    )
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())
