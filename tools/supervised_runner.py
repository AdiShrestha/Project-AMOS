#!/usr/bin/env python3
"""Production subprocess supervisor, attempt manager, and execution receipt logger for Project AMOS / BPFeat.

Systematically resolves legacy audit finding F01:
1. Executes real target binaries and Python tools with explicit argument ABIs.
2. Enforces hard process deadline timeouts with process tree termination (SIGTERM -> SIGKILL).
3. Preserves complete raw stdout.log, stderr.log, exit codes, and timestamps.
4. Enforces immutable attempt directory allocation (attempt0001, attempt0002, etc.).
   Prior attempts are permanent evidence and are never deleted or overwritten.
5. Computes cryptographic SHA-256 bindings: inputs_before, inputs_after, binary_sha256,
   launch_spec digest, output hashes, and canonical UUID4 run_nonce in execution_record.json.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import uuid

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent


class ExitStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    SIGNALED = "SIGNALED"


def validate_uuid4(nonce: str) -> str:
    """Validate that a string is a canonical version-4 UUID."""
    try:
        parsed = uuid.UUID(nonce)
    except (ValueError, AttributeError):
        parsed = None
    if parsed is None or parsed.version != 4 or str(parsed) != nonce:
        raise ValueError(f"invalid UUID4 nonce: {nonce!r}")
    return nonce


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a regular file."""
    if not path.is_file():
        raise FileNotFoundError(f"cannot hash non-file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inventory_files(directory: Path, exclude_names: Optional[Set[str]] = None) -> Dict[str, str]:
    """Inventory all regular files in a directory and return {rel_path: sha256}."""
    if not directory.exists() or not directory.is_dir():
        return {}
    exclude = exclude_names or set()
    result: Dict[str, str] = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.name not in exclude:
            rel = str(p.relative_to(directory))
            result[rel] = file_sha256(p)
    return result


def allocate_attempt_directory(run_dir: Path) -> Tuple[int, Path]:
    """Find the next sequential immutable attempt directory {run_dir}/attemptNNNN."""
    run_dir.mkdir(parents=True, exist_ok=True)
    existing_attempts = []
    for entry in run_dir.iterdir():
        if entry.is_dir() and re.fullmatch(r"attempt\d{4}", entry.name):
            try:
                num = int(entry.name[7:])
                existing_attempts.append(num)
            except ValueError:
                pass
    next_num = max(existing_attempts, default=0) + 1
    attempt_dir = run_dir / f"attempt{next_num:04d}"
    return next_num, attempt_dir


@dataclass
class ExecutionReceipt:
    run_nonce: str
    experiment_id: str
    seed: int
    attempt_number: int
    attempt_dir: str
    executable: str
    binary_sha256: Optional[str]
    argv: List[str]
    launch_spec_sha256: str
    inputs_before: Dict[str, str]
    inputs_after: Dict[str, str]
    inputs_unmodified: bool
    outputs: Dict[str, str]
    exit_code: Optional[int]
    exit_status: str
    termination_signal: Optional[int]
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SubprocessSupervisor:
    """Subprocess supervisor managing timeouts, process groups, and cryptographic audit records."""

    def __init__(self, default_timeout_seconds: float = 60.0) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    def execute(
        self,
        executable: Union[str, Path],
        args: Sequence[str],
        run_dir: Path,
        experiment_id: str = "EXP",
        seed: int = 42,
        input_files: Optional[Sequence[Path]] = None,
        timeout_seconds: Optional[float] = None,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ExecutionReceipt:
        """Run an executable under supervision, generating an immutable attempt folder and receipt."""
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t0_monotonic = time.perf_counter()
        run_nonce = validate_uuid4(str(uuid.uuid4()))

        run_dir = Path(run_dir)
        attempt_num, attempt_dir = allocate_attempt_directory(run_dir)

        exec_path = Path(executable)
        is_binary = exec_path.is_file() and os.access(exec_path, os.X_OK)

        # Inventory input files before launch
        inputs_before: Dict[str, str] = {}
        input_paths: List[Path] = [Path(p) for p in (input_files or [])]
        for ip in input_paths:
            if ip.is_file():
                inputs_before[str(ip)] = file_sha256(ip)

        binary_hash: Optional[str] = None
        if exec_path.is_file():
            binary_hash = file_sha256(exec_path)

        # Build final argument list replacing placeholders
        final_argv: List[str] = [str(exec_path)]
        for arg in args:
            if "{out_dir}" in arg:
                arg = arg.replace("{out_dir}", str(attempt_dir))
            if "{seed}" in arg:
                arg = arg.replace("{seed}", str(seed))
            final_argv.append(str(arg))

        launch_spec_hash = hashlib.sha256(json.dumps(final_argv).encode("utf-8")).hexdigest()

        # Pre-flight check: Exists and is executable (F01 Remediation)
        if not exec_path.is_file():
            attempt_dir.mkdir(parents=True, exist_ok=True)
            err_msg = f"Executable not found or not a regular file: {exec_path}"
            (attempt_dir / "stderr.log").write_text(f"ENGINE_FAILED: {err_msg}\n", encoding="utf-8")
            (attempt_dir / "stdout.log").write_text("", encoding="utf-8")

            t1_monotonic = time.perf_counter()
            finished_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

            outputs = inventory_files(attempt_dir, exclude_names={"execution_record.json"})
            receipt = ExecutionReceipt(
                run_nonce=run_nonce,
                experiment_id=experiment_id,
                seed=seed,
                attempt_number=attempt_num,
                attempt_dir=str(attempt_dir),
                executable=str(exec_path),
                binary_sha256=binary_hash,
                argv=final_argv,
                launch_spec_sha256=launch_spec_hash,
                inputs_before=inputs_before,
                inputs_after=inputs_before,
                inputs_unmodified=True,
                outputs=outputs,
                exit_code=127,
                exit_status=ExitStatus.FAILED.value,
                termination_signal=None,
                started_at_utc=started_utc,
                finished_at_utc=finished_utc,
                elapsed_seconds=max(0.0, t1_monotonic - t0_monotonic),
                error_message=err_msg,
            )
            with (attempt_dir / "execution_record.json").open("w", encoding="utf-8") as f:
                json.dump(receipt.to_dict(), f, indent=2)
            return receipt

        # Process execution with process-tree isolation and deadline watchdog
        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)

        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []
        exit_code: Optional[int] = None
        exit_status = ExitStatus.COMPLETED.value
        term_signal: Optional[int] = None
        error_msg: Optional[str] = None

        try:
            # Use start_new_session=True to establish distinct process group for clean killpg
            proc = subprocess.Popen(
                final_argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=proc_env,
                start_new_session=True,
            )

            try:
                out_b, err_b = proc.communicate(timeout=timeout)
                stdout_chunks.append(out_b)
                stderr_chunks.append(err_b)
                exit_code = proc.returncode

                if exit_code != 0:
                    exit_status = ExitStatus.FAILED.value
                    error_msg = f"Process exited with non-zero code {exit_code}"

            except subprocess.TimeoutExpired:
                # Deadline watchdog triggered: terminate process group and process
                exit_status = ExitStatus.TIMED_OUT.value
                error_msg = f"Process exceeded deadline timeout of {timeout}s"

                # Step 1: SIGTERM process group and process
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                try:
                    proc.terminate()
                except (ProcessLookupError, OSError):
                    pass

                # Step 2: Grace period
                time.sleep(0.5)

                # Step 3: Escalate to SIGKILL if still running
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                try:
                    proc.kill()
                except (ProcessLookupError, OSError):
                    pass

                try:
                    out_b, err_b = proc.communicate(timeout=2.0)
                    stdout_chunks.append(out_b)
                    stderr_chunks.append(err_b)
                except Exception:
                    pass

                stderr_chunks.append(f"\n[SUPERVISOR_TIMEOUT]: Process exceeded deadline timeout of {timeout}s; terminated.\n".encode("utf-8"))
                exit_code = proc.returncode if proc.returncode is not None else -signal.SIGKILL
                term_signal = signal.SIGKILL

        except Exception as e:
            exit_status = ExitStatus.FAILED.value
            exit_code = -1
            error_msg = f"Supervisor launch exception: {e}"
            stderr_chunks.append(f"{error_msg}\n".encode("utf-8"))

        t1_monotonic = time.perf_counter()
        finished_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        elapsed = max(0.0, t1_monotonic - t0_monotonic)

        # Ensure attempt directory exists to capture artifacts
        attempt_dir.mkdir(parents=True, exist_ok=True)

        # Write captured standard streams
        combined_stdout = b"".join(stdout_chunks)
        combined_stderr = b"".join(stderr_chunks)
        (attempt_dir / "stdout.log").write_bytes(combined_stdout)
        (attempt_dir / "stderr.log").write_bytes(combined_stderr)

        # Post-execution input immutability audit
        inputs_after: Dict[str, str] = {}
        inputs_unmodified = True
        for ip in input_paths:
            if ip.is_file():
                h_after = file_sha256(ip)
                inputs_after[str(ip)] = h_after
                if inputs_before.get(str(ip)) != h_after:
                    inputs_unmodified = False
            else:
                inputs_unmodified = False

        if not inputs_unmodified:
            exit_status = ExitStatus.FAILED.value
            error_msg = (error_msg or "") + " [AUDIT_ERROR: Input files mutated during execution]"

        # Inventory attempt directory outputs (excluding execution_record.json)
        outputs = inventory_files(attempt_dir, exclude_names={"execution_record.json"})

        receipt = ExecutionReceipt(
            run_nonce=run_nonce,
            experiment_id=experiment_id,
            seed=seed,
            attempt_number=attempt_num,
            attempt_dir=str(attempt_dir),
            executable=str(exec_path),
            binary_sha256=binary_hash,
            argv=final_argv,
            launch_spec_sha256=launch_spec_hash,
            inputs_before=inputs_before,
            inputs_after=inputs_after,
            inputs_unmodified=inputs_unmodified,
            outputs=outputs,
            exit_code=exit_code,
            exit_status=exit_status,
            termination_signal=term_signal,
            started_at_utc=started_utc,
            finished_at_utc=finished_utc,
            elapsed_seconds=elapsed,
            error_message=error_msg,
        )

        # Write structured execution record into immutable attempt directory
        record_path = attempt_dir / "execution_record.json"
        with record_path.open("w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)

        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Supervised runner for Project AMOS executables")
    parser.add_argument("--executable", "-e", type=Path, default=Path("build/debug/bpfeat_engine"), help="Target executable path")
    parser.add_argument("--experiment-id", type=str, default="EXP_LOCAL", help="Experiment identifier")
    parser.add_argument("--run-dir", "-r", type=Path, default=Path("results/EXP_LOCAL"), help="Base run directory")
    parser.add_argument("--seed", type=int, default=42, help="Seed integer")
    parser.add_argument("--timeout", type=float, default=60.0, help="Process deadline timeout seconds")
    parser.add_argument("--events", type=Path, help="Input events CSV")
    parser.add_argument("--model", type=Path, help="Input model weights file")
    parser.add_argument("--mode", type=str, default="fixed", help="Execution mode (fixed|batch|alpha|joint)")

    args, unknown = parser.parse_known_args()

    input_files: List[Path] = []
    exec_args: List[str] = []

    if args.events:
        input_files.append(args.events)
        exec_args.extend(["--events", str(args.events)])
    if args.model:
        input_files.append(args.model)
        exec_args.extend(["--model", str(args.model)])

    exec_args.extend(["--out-dir", "{out_dir}", "--mode", args.mode])
    exec_args.extend(unknown)

    supervisor = SubprocessSupervisor(default_timeout_seconds=args.timeout)
    print(f"Launching supervised execution of {args.executable} in {args.run_dir}...", file=sys.stderr)

    receipt = supervisor.execute(
        executable=args.executable,
        args=exec_args,
        run_dir=args.run_dir,
        experiment_id=args.experiment_id,
        seed=args.seed,
        input_files=input_files,
        timeout_seconds=args.timeout,
    )

    print(f"Execution finished with status: {receipt.exit_status} (exit code: {receipt.exit_code})", file=sys.stderr)
    print(f"Attempt Directory: {receipt.attempt_dir}", file=sys.stderr)
    print(f"Receipt Digest: {receipt.run_nonce}", file=sys.stderr)
    print(f"Outputs Captured: {list(receipt.outputs.keys())}", file=sys.stderr)

    sys.exit(0 if receipt.exit_status == ExitStatus.COMPLETED.value else 1)


if __name__ == "__main__":
    main()
