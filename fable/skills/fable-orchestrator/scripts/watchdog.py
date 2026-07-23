#!/usr/bin/env python3
"""Enforce an Ask deadline against a controller-owned worker process group."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any


TERMINAL = {"done", "failed", "empty-output", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_status(run: Path) -> str:
    try:
        value = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    return str(value.get("status", "unknown"))


def write_evidence(run: Path, value: dict[str, Any]) -> None:
    target = run / "watchdog.json"
    temporary = run / f".watchdog.{os.getpid()}.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, target)
    target.chmod(0o600)
    directory = os.open(run, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def termination_lock(run: Path):
    path = run / ".termination.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.chmod(path, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def process_group_members(pgid: int) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,pgid=,stat="],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [{"pid": -1, "pgid": pgid, "stat": "inventory_failed"}]
    if result.returncode != 0:
        return [{"pid": -1, "pgid": pgid, "stat": "inventory_failed"}]
    members: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid_value = int(parts[0])
            pgid_value = int(parts[1])
        except ValueError:
            continue
        if pgid_value == pgid:
            members.append({"pid": pid_value, "pgid": pgid_value, "stat": parts[2]})
    return members


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def liveness(pid: int, pgid: int) -> dict[str, Any]:
    members = process_group_members(pgid)
    return {
        "pid_alive": pid_alive(pid),
        "group_alive": bool(members),
        "remaining_members": members,
    }


def wait_group_gone(pid: int, pgid: int, seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    current = liveness(pid, pgid)
    while (
        current["pid_alive"] or current["group_alive"]
    ) and time.monotonic() < deadline:
        time.sleep(0.05)
        current = liveness(pid, pgid)
    return current


def send_group_signal(pgid: int, sig: signal.Signals) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "signal": sig.name,
        "attempted": True,
        "sent": False,
        "error": None,
    }
    try:
        os.killpg(pgid, sig)
        outcome["sent"] = True
    except ProcessLookupError:
        outcome["error"] = "process_group_not_found"
    except (PermissionError, OSError) as exc:
        outcome["error"] = str(exc)
    return outcome


def load_complete_supervision(path: Path, wait_s: float = 2.0) -> dict[str, Any]:
    deadline = time.monotonic() + wait_s
    last_error = "missing"
    while time.monotonic() < deadline:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(0.02)
            continue
        if (
            isinstance(value, dict)
            and value.get("identity_ready") is True
            and value.get("watchdog_started") is True
        ):
            return value
        last_error = "incomplete"
        time.sleep(0.02)
    raise ValueError(f"supervision identity is {last_error}")


def load_target(args: argparse.Namespace, trigger: str) -> tuple[dict[str, Any], int, int, float, float]:
    base_evidence: dict[str, Any] = {
        "kind": "controller_worker_termination",
        "trigger": trigger,
        "deadline_enforced": False,
        "termination_verified": False,
        "cancel_transport": str(args.wrapper),
        "recorded_at": now(),
    }
    try:
        supervision = load_complete_supervision(args.supervision)
        target_pid = supervision["target_pid"]
        target_pgid = supervision["target_pgid"]
        timeout_s = float(supervision["timeout_s"])
        grace_s = float(supervision["grace_s"])
        deadline_epoch = float(supervision["deadline_epoch"])
        if (
            type(target_pid) is not int
            or type(target_pgid) is not int
            or target_pid <= 1
            or target_pgid <= 1
            or target_pid != target_pgid
            or supervision.get("mode") != "setsid_process_group"
            or supervision.get("run_id") != args.run_id
            or not math.isfinite(timeout_s)
            or timeout_s <= 0
            or not math.isfinite(grace_s)
            or grace_s <= 0
            or not math.isfinite(deadline_epoch)
        ):
            raise ValueError("supervision identity fields are incoherent")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        base_evidence["failure"] = f"missing or invalid supervision identity: {exc}"
        write_evidence(args.run_dir, base_evidence)
        raise

    base_evidence.update(
        {
            "target_pid": target_pid,
            "target_pgid": target_pgid,
            "timeout_s": timeout_s,
            "grace_s": grace_s,
            "supervision_sha256": hashlib.sha256(
                args.supervision.read_bytes()
            ).hexdigest(),
        }
    )
    return base_evidence, target_pid, target_pgid, grace_s, deadline_epoch


def existing_verified_explicit_cancel(run: Path) -> bool:
    try:
        evidence = json.loads((run / "watchdog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(evidence, dict)
        and evidence.get("trigger") == "explicit_cancel"
        and evidence.get("termination_verified") is True
    )


def terminate_and_verify(
    args: argparse.Namespace,
    *,
    trigger: str,
    cancel_exit_code: int | None,
    cancel_stdout: str = "",
    cancel_stderr: str = "",
    observed_status: str | None = None,
) -> int:
    try:
        base_evidence, target_pid, target_pgid, grace_s, _ = load_target(args, trigger)
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return 2
    with termination_lock(args.run_dir):
        if trigger == "observed_cancelled" and existing_verified_explicit_cancel(
            args.run_dir
        ):
            return 0
        before_term = liveness(target_pid, target_pgid)
        term = send_group_signal(target_pgid, signal.SIGTERM)
        after_term = wait_group_gone(target_pid, target_pgid, grace_s)
        kill: dict[str, Any] = {
            "signal": "SIGKILL",
            "attempted": False,
            "sent": False,
            "error": None,
        }
        if after_term["pid_alive"] or after_term["group_alive"]:
            kill = send_group_signal(target_pgid, signal.SIGKILL)
        final_liveness = wait_group_gone(
            target_pid, target_pgid, max(1.0, grace_s)
        )
        verified = (
            not final_liveness["pid_alive"]
            and not final_liveness["group_alive"]
            and final_liveness["remaining_members"] == []
        )
        operation_succeeded = verified and cancel_exit_code in {None, 0}
        evidence = {
            **base_evidence,
            "deadline_enforced": trigger == "deadline" and operation_succeeded,
            "termination_verified": verified,
            "cancel_exit_code": cancel_exit_code,
            "cancel_stdout_sha256": hashlib.sha256(
                cancel_stdout.encode()
            ).hexdigest(),
            "cancel_stderr_excerpt": cancel_stderr[-1_000:],
            "observed_terminal_status": observed_status,
            "liveness_before_term": before_term,
            "term": term,
            "liveness_after_term": after_term,
            "kill": kill,
            "final_liveness": final_liveness,
            "recorded_at": now(),
        }
        if not operation_succeeded:
            evidence["failure"] = (
                "worker process group remained live or wrapper cancel failed"
            )
        write_evidence(args.run_dir, evidence)
        return 0 if operation_succeeded else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrapper", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--supervision", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("monitor", "terminate"), default="monitor"
    )
    parser.add_argument("--trigger", default="explicit_cancel")
    parser.add_argument("--cancel-exit-code", type=int)
    args = parser.parse_args()
    if args.mode == "terminate":
        return terminate_and_verify(
            args,
            trigger=args.trigger,
            cancel_exit_code=args.cancel_exit_code,
        )
    try:
        _, target_pid, target_pgid, _, deadline_epoch = load_target(args, "deadline")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return 2
    while True:
        status = read_status(args.run_dir)
        if status in TERMINAL:
            current = liveness(target_pid, target_pgid)
            if (
                status == "cancelled"
                or current["pid_alive"]
                or current["group_alive"]
            ):
                return terminate_and_verify(
                    args,
                    trigger=(
                        "observed_cancelled"
                        if status == "cancelled"
                        else "observed_terminal_live"
                    ),
                    cancel_exit_code=None,
                    observed_status=status,
                )
            return 0
        remaining = deadline_epoch - time.time()
        if remaining <= 0:
            break
        time.sleep(min(0.25, remaining))

    try:
        cancel = subprocess.run(
            [str(args.wrapper), "cancel", args.run_id],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
            env=dict(os.environ),
        )
        cancel_exit_code = cancel.returncode
        cancel_stdout = cancel.stdout
        cancel_stderr = cancel.stderr
    except subprocess.TimeoutExpired as exc:
        cancel_exit_code = 124
        cancel_stdout = str(exc.stdout or "")
        cancel_stderr = f"installed cancel timed out: {exc}"
    except OSError as exc:
        cancel_exit_code = 127
        cancel_stdout = ""
        cancel_stderr = f"installed cancel could not execute: {exc}"
    return terminate_and_verify(
        args,
        trigger="deadline",
        cancel_exit_code=cancel_exit_code,
        cancel_stdout=cancel_stdout,
        cancel_stderr=cancel_stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
