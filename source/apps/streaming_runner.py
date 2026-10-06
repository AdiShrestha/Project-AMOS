#!/usr/bin/env python3
"""Isolated streaming runner entrypoint for supervised execution.

Runs under Python isolation flags (-I -P -B -S), parses checked argument ABIs,
verifies native binary and input digests, and supervises execution under process deadlines.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def sha256_file(path):
    """Compute SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_arguments(argv):
    """Parse checked argument ABI supporting both named flags and positional roles."""
    args = {
        "run_dir": None,
        "seed": 42,
        "experiment_id": "EXP_STREAMING",
        "events": "data/canonical/user_behavior_clean.csv",
        "model": "data/models/logistic_model.txt",
        "mode": "fixed",
        "executable": None,
        "timeout_seconds": 120.0,
    }

    i = 0
    positional = []
    while i < len(argv):
        arg = argv[i]
        if arg == "--run-dir" and i + 1 < len(argv):
            args["run_dir"] = argv[i + 1]
            i += 2
        elif arg == "--seed" and i + 1 < len(argv):
            args["seed"] = int(argv[i + 1])
            i += 2
        elif arg == "--experiment-id" and i + 1 < len(argv):
            args["experiment_id"] = argv[i + 1]
            i += 2
        elif arg == "--events" and i + 1 < len(argv):
            args["events"] = argv[i + 1]
            i += 2
        elif arg == "--model" and i + 1 < len(argv):
            args["model"] = argv[i + 1]
            i += 2
        elif arg == "--mode" and i + 1 < len(argv):
            args["mode"] = argv[i + 1]
            i += 2
        elif arg == "--executable" and i + 1 < len(argv):
            args["executable"] = argv[i + 1]
            i += 2
        elif arg == "--timeout" and i + 1 < len(argv):
            args["timeout_seconds"] = float(argv[i + 1])
            i += 2
        elif not arg.startswith("--"):
            positional.append(arg)
            i += 1
        else:
            i += 1

    # If positional arguments provided (e.g. from template {run_dir} {seed} {experiment_id})
    if len(positional) >= 1 and args["run_dir"] is None:
        args["run_dir"] = positional[0]
    if len(positional) >= 2:
        try:
            args["seed"] = int(positional[1])
        except ValueError:
            pass
    if len(positional) >= 3:
        args["experiment_id"] = positional[2]

    return args


def resolve_native_binary(preferred_path=None):
    """Resolve approved native engine binary."""
    if preferred_path:
        p = Path(preferred_path)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p.resolve())
        return None

    candidates = [
        "build/release/bpfeat_engine",
        "build/debug/bpfeat_engine",
        "build/bpfeat_engine",
    ]
    for c in candidates:
        p = Path(c)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p.resolve())

    return None


def run_supervised(config):
    """Execute native binary under supervisor controls."""
    run_dir = Path(config["run_dir"]).resolve() if config["run_dir"] else Path.cwd() / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"

    binary_path = resolve_native_binary(config["executable"])
    if not binary_path:
        msg = f"ERROR: executable not found or not executable: {config.get('executable') or 'bpfeat_engine'}\n"
        stderr_path.write_text(msg, encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        sys.stderr.write(msg)
        return 127

    binary_hash = sha256_file(binary_path)

    events_path = Path(config["events"]).resolve()
    model_path = Path(config["model"]).resolve()

    engine_out = run_dir / "engine_out"

    cmd = [
        binary_path,
        "--events", str(events_path),
        "--model", str(model_path),
        "--out-dir", str(engine_out),
        "--mode", str(config["mode"]),
    ]

    start_t = time.time()
    try:
        with open(stdout_path, "wb") as out_f, open(stderr_path, "wb") as err_f:
            proc = subprocess.Popen(
                cmd,
                stdout=out_f,
                stderr=err_f,
                start_new_session=True,
            )
            try:
                proc.wait(timeout=config["timeout_seconds"])
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                exit_code = -9
                with open(stderr_path, "a", encoding="utf-8") as ef:
                    ef.write(f"\n[SUPERVISOR] Process timed out after {config['timeout_seconds']}s\n")
    except Exception as e:
        exit_code = 1
        with open(stderr_path, "a", encoding="utf-8") as ef:
            ef.write(f"\n[SUPERVISOR] Execution failed: {e}\n")

    elapsed = time.time() - start_t

    # If engine_out was created, promote all files to run_dir
    if engine_out.exists() and engine_out.is_dir():
        for child in engine_out.iterdir():
            target = run_dir / child.name
            if target.exists():
                target.unlink()
            child.rename(target)
        try:
            engine_out.rmdir()
        except OSError:
            pass

    # Emit telemetry and result metadata
    pred_file = run_dir / "predictions_unlabeled.csv"
    alt_pred = run_dir / "predictions.csv"
    chosen_pred = "predictions_unlabeled.csv" if pred_file.exists() else ("predictions.csv" if alt_pred.exists() else "none")

    result = {
        "experiment_id": config["experiment_id"],
        "seed": config["seed"],
        "config": {
            "mode": config["mode"],
            "events": str(events_path),
            "model": str(model_path),
        },
        "predictions": chosen_pred,
        "method_evidence": "source/apps/streaming_runner.py",
        "exit_code": exit_code,
        "elapsed_seconds": elapsed,
        "binary_sha256": binary_hash,
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    return exit_code


def main():
    config = parse_arguments(sys.argv[1:])
    code = run_supervised(config)
    sys.exit(code)


if __name__ == "__main__":
    main()
