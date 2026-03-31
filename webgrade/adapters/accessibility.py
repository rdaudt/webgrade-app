from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


def _resolve_pa11y_command() -> list[str]:
    repo_root = Path(__file__).resolve().parents[2]
    local_pa11y = repo_root / "node_modules" / ".bin" / "pa11y.cmd"
    if local_pa11y.exists():
        return [str(local_pa11y)]
    npx_command = shutil.which("npx.cmd") or shutil.which("npx")
    if npx_command:
        return [npx_command, "--yes", "pa11y"]
    raise RuntimeError("Pa11y is not available. Install it locally or make npx available.")


def _bucket_level(issue: dict[str, Any]) -> str | None:
    code = str(issue.get("code", ""))
    match = re.search(r"WCAG2(AAA|AA|A)", code)
    return match.group(1).lower() if match else None


def _execute_pa11y(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError("Pa11y is not available. Install it locally or make npx available.") from exc


def run_pa11y(url: str) -> dict[str, Any]:
    command = _resolve_pa11y_command() + [
        url,
        "--reporter",
        "json",
        "--standard",
        "WCAG2AAA",
        "--timeout",
        "30000",
    ]
    last_error: RuntimeError | None = None
    completed: subprocess.CompletedProcess[str] | None = None
    for _attempt in range(2):
        completed = _execute_pa11y(command)
        if completed.returncode in {0, 2}:
            break
        stderr = completed.stderr.strip() or completed.stdout.strip()
        last_error = RuntimeError(f"Pa11y failed: {stderr or 'unknown error'}")
    if completed is None:
        raise RuntimeError("Pa11y execution did not start")
    if completed.returncode not in {0, 2}:
        if last_error is not None:
            raise last_error
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Pa11y failed: {stderr or 'unknown error'}")

    issues = json.loads(completed.stdout or "[]")
    counts = {"a": 0, "aa": 0, "aaa": 0}
    for issue in issues:
        level = _bucket_level(issue)
        if level in counts:
            counts[level] += 1
    weighted_issue_count = (3 * counts["a"]) + (2 * counts["aa"]) + counts["aaa"]
    summary = {
        "issue_count_total": len(issues),
        "count_a": counts["a"],
        "count_aa": counts["aa"],
        "count_aaa": counts["aaa"],
        "weighted_issue_count": weighted_issue_count,
    }
    return {
        "adapter_key": "pa11y",
        "viewport": "combined",
        "status": "ok",
        "summary": summary,
        "raw": {"issues": issues},
        "error": None,
    }
