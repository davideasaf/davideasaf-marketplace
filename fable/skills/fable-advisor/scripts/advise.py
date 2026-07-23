#!/usr/bin/env python3
"""Run a read-only Fable consultation through Cursor's agent CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4


DEFAULT_MODEL = "claude-fable-5-thinking-high"
DEFAULT_TIMEOUT = 300
ADVISORY_PREFIX = """You are Fable, an on-demand advisor. Codex remains executor.
Fable must not edit files, run state-changing shell commands, or mutate external systems through MCPs.
You may perform read-only workspace and MCP analysis. Respond only with your advisory analysis.

"""
ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def available_models(output: str) -> list[str]:
    """Extract model IDs from Cursor's human- or JSON-formatted model listing."""
    models: list[str] = []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                models.append(item)
            elif isinstance(item, dict) and isinstance(item.get("id"), str):
                models.append(item["id"])
    elif isinstance(data, dict):
        entries = data.get("models", [])
        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, str):
                    models.append(item)
                elif isinstance(item, dict) and isinstance(item.get("id"), str):
                    models.append(item["id"])
    if not models:
        models = [
            line.strip().split(" - ", 1)[0]
            for line in output.splitlines()
            if line.strip()
        ]
    return models


def last_json_object(output: str) -> dict[str, object] | None:
    """Accept one JSON object or the final complete JSON line."""
    stripped = output.strip()
    if stripped:
        try:
            item = json.loads(stripped)
            if isinstance(item, dict):
                return item
        except json.JSONDecodeError:
            pass
    for line in reversed(output.splitlines()):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            return item
    return None


def response_from(payload: dict[str, object]) -> str | None:
    for key in ("result", "response", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def ensure_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def write_run_file(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            descriptor = -1
            file.write(content)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def sanitized_diagnostic(content: str | bytes | None) -> str:
    if content is None:
        return ""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    content = ANSI_ESCAPE.sub("", content)
    return "".join(
        character
        for character in content
        if character in "\n\t" or 0x20 <= ord(character) < 0x7F or ord(character) >= 0xA0
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask Fable for read-only advice.")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace to analyze.")
    parser.add_argument("--with-mcps", action="store_true", help="Permit read-only MCP analysis.")
    parser.add_argument("--resume", help="Explicit Cursor session ID to resume.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("prompt_or_dash", metavar="PROMPT_OR_DASH")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    brief = sys.stdin.read() if args.prompt_or_dash == "-" else args.prompt_or_dash
    prompt = ADVISORY_PREFIX + brief
    workspace = str(Path(args.workspace).expanduser().resolve())
    state_dir = Path(os.environ.get("FABLE_ADVISOR_STATE_DIR", "~/.cache/fable-advisor")).expanduser()
    run_id = uuid4().hex
    run_dir = state_dir / run_id
    ensure_private_dir(state_dir)
    run_dir.mkdir(mode=0o700, exist_ok=False)
    run_dir.chmod(0o700)
    prompt_path = run_dir / "prompt.txt"
    response_path = run_dir / "response.txt"
    meta_path = run_dir / "meta.json"
    write_run_file(prompt_path, prompt)

    started_at = utc_timestamp()
    started_clock = time.monotonic()
    agent_bin = os.environ.get("FABLE_ADVISOR_AGENT_BIN", "agent")
    response = ""
    returned_session_id: str | None = None
    exit_code = 1
    terminal_status = "unknown_failure"
    error = ""
    diagnostics: dict[str, str] = {}

    def finish() -> int:
        ended_at = utc_timestamp()
        write_run_file(response_path, response)
        for filename, content in diagnostics.items():
            write_run_file(run_dir / filename, sanitized_diagnostic(content))
        meta: dict[str, object] = {
            "run_id": run_id,
            "model": args.model,
            "workspace": workspace,
            "with_mcps": args.with_mcps,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": round(time.monotonic() - started_clock, 6),
            "exit_code": exit_code,
            "terminal_status": terminal_status,
            "returned_session_id": returned_session_id,
        }
        if args.resume is not None:
            meta["resumed_session_id"] = args.resume
        if error:
            meta["error"] = error
        write_run_file(meta_path, json.dumps(meta, indent=2, sort_keys=True) + "\n")
        if error:
            print(error, file=sys.stderr)
        print(f"FABLE_ADVISOR_META={meta_path.resolve()}", file=sys.stderr)
        return exit_code

    if not Path(workspace).exists():
        exit_code, terminal_status = 2, "workspace_missing"
        error = f"Fable workspace does not exist: {workspace}"
        return finish()
    if not Path(workspace).is_dir():
        exit_code, terminal_status = 2, "workspace_not_directory"
        error = f"Fable workspace is not a directory: {workspace}"
        return finish()

    try:
        models_result = subprocess.run(
            [agent_bin, "models"], text=True, capture_output=True, timeout=args.timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        diagnostics.update({
            "model-check.stdout.txt": sanitized_diagnostic(exc.stdout),
            "model-check.stderr.txt": sanitized_diagnostic(exc.stderr),
        })
        exit_code, terminal_status = 124, "timed_out"
        error = f"Fable model listing timed out after {args.timeout:g} seconds."
        return finish()
    except OSError as exc:
        exit_code, terminal_status = 127, "agent_launch_failed"
        error = f"Could not start Fable agent '{agent_bin}': {exc}"
        return finish()

    models = available_models(models_result.stdout)
    if models_result.returncode != 0:
        diagnostics.update({
            "model-check.stdout.txt": models_result.stdout,
            "model-check.stderr.txt": models_result.stderr,
        })
        exit_code, terminal_status = models_result.returncode or 1, "model_check_failed"
        error = f"Fable model check failed with exit code {models_result.returncode}."
        return finish()
    if args.model not in models:
        diagnostics.update({
            "model-check.stdout.txt": models_result.stdout,
            "model-check.stderr.txt": models_result.stderr,
        })
        exit_code, terminal_status = 2, "model_unavailable"
        variants = [model for model in models if "fable" in model.lower()]
        available = ", ".join(variants) if variants else "(none reported)"
        error = f"Requested Fable model '{args.model}' is unavailable. Available Fable variants: {available}"
        return finish()

    command = [
        agent_bin, "-p", "--model", args.model, "--output-format", "json", "--trust",
        "--mode", "ask", "--sandbox", "enabled", "--workspace", workspace,
    ]
    if args.with_mcps:
        command.append("--approve-mcps")
    if args.resume is not None:
        command.extend(["--resume", args.resume])
    command.append(prompt)
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        diagnostics.update({
            "agent.stdout.txt": sanitized_diagnostic(exc.stdout),
            "agent.stderr.txt": sanitized_diagnostic(exc.stderr),
        })
        exit_code, terminal_status = 124, "timed_out"
        error = f"Fable consultation timed out after {args.timeout:g} seconds."
        return finish()
    except OSError as exc:
        exit_code, terminal_status = 127, "agent_launch_failed"
        error = f"Could not start Fable agent '{agent_bin}': {exc}"
        return finish()

    payload = last_json_object(result.stdout)
    if payload is not None and isinstance(payload.get("session_id"), str):
        candidate_session_id = payload["session_id"].strip()
        if candidate_session_id:
            returned_session_id = candidate_session_id
    if result.returncode != 0:
        diagnostics.update({
            "agent.stdout.txt": result.stdout,
            "agent.stderr.txt": result.stderr,
        })
        exit_code, terminal_status = result.returncode, "agent_nonzero"
        error = f"Fable consultation exited with code {result.returncode}."
        return finish()
    if payload is None:
        diagnostics.update({
            "agent.stdout.txt": result.stdout,
            "agent.stderr.txt": result.stderr,
        })
        exit_code, terminal_status = 1, "invalid_json"
        error = "Fable consultation returned invalid JSON output."
        return finish()
    parsed_response = response_from(payload)
    if parsed_response is None or not parsed_response.strip():
        diagnostics.update({
            "agent.stdout.txt": result.stdout,
            "agent.stderr.txt": result.stderr,
        })
        exit_code, terminal_status = 1, "blank_response"
        error = "Fable consultation returned a blank response."
        return finish()

    response = parsed_response
    if returned_session_id is None:
        diagnostics.update({
            "agent.stdout.txt": result.stdout,
            "agent.stderr.txt": result.stderr,
        })
        exit_code, terminal_status = 1, "missing_session_id"
        error = "Fable consultation returned a response without a nonblank session ID."
        return finish()
    exit_code, terminal_status = 0, "done"
    outcome = finish()
    print(response)
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
