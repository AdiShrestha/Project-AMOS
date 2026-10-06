"""Adversarial and property test suite for the subprocess supervisor and execution receipts.

Verifies:
1. F01 remediation: nonexistent executable fails cleanly with status FAILED and explanatory stderr.
2. Timeout enforcement: deadline watchdog kills hung process trees and records TIMED_OUT.
3. Attempt immutability: retries create sequential attempt directories without deleting prior attempts.
4. Cryptographic hash integrity: input and output hashes match disk bytes exactly.
5. Input mutation detection: malicious or accidental in-place alteration of input files fails audit.
6. Real native execution: supervised run of build/debug/bpfeat_engine passes and generates valid predictions.
7. Real native cache tool execution: supervised run of build/debug/bpfeat_cache_tool passes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
for _p in (str(_project_root), str(_script_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.supervised_runner import (
    ExitStatus,
    SubprocessSupervisor,
    file_sha256,
    validate_uuid4,
)


class TestSupervisedRunner(unittest.TestCase):
    """Test suite for process supervision, deadline enforcement, and receipt integrity."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.supervisor = SubprocessSupervisor(default_timeout_seconds=30.0)

    def test_f01_remediation_nonexistent_executable_fails(self):
        """Verify F01 defect remediation: missing binary fails immediately with non-zero exit."""
        fake_binary = self.root / "nonexistent_binary"
        run_dir = self.root / "exp_f01"

        receipt = self.supervisor.execute(
            executable=fake_binary,
            args=["--flag", "value"],
            run_dir=run_dir,
            experiment_id="EXP_F01",
            seed=42,
        )

        self.assertEqual(receipt.exit_status, ExitStatus.FAILED.value)
        self.assertEqual(receipt.exit_code, 127)
        self.assertIn("Executable not found", receipt.error_message or "")

        attempt_dir = Path(receipt.attempt_dir)
        self.assertTrue(attempt_dir.is_dir())
        self.assertTrue((attempt_dir / "stderr.log").exists())
        self.assertTrue((attempt_dir / "stdout.log").exists())
        self.assertTrue((attempt_dir / "execution_record.json").exists())

        stderr_content = (attempt_dir / "stderr.log").read_text(encoding="utf-8")
        self.assertIn("Executable not found", stderr_content)

        # Validate cryptographic receipt metadata
        record = json.loads((attempt_dir / "execution_record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["run_nonce"], receipt.run_nonce)
        self.assertEqual(validate_uuid4(record["run_nonce"]), receipt.run_nonce)
        self.assertEqual(record["exit_status"], ExitStatus.FAILED.value)
        self.assertEqual(record["exit_code"], 127)

    def test_timeout_watchdog_kills_hung_process(self):
        """Verify deadline watchdog terminates runaway processes and records TIMED_OUT."""
        run_dir = self.root / "exp_timeout"

        # Launch process that sleeps for 10 seconds with a 0.5s deadline
        receipt = self.supervisor.execute(
            executable=sys.executable,
            args=["-c", "import time; time.sleep(10)"],
            run_dir=run_dir,
            experiment_id="EXP_TIMEOUT",
            seed=42,
            timeout_seconds=0.5,
        )

        self.assertEqual(receipt.exit_status, ExitStatus.TIMED_OUT.value)
        self.assertLess(receipt.elapsed_seconds, 3.0)

        attempt_dir = Path(receipt.attempt_dir)
        self.assertTrue(attempt_dir.is_dir())
        stderr_content = (attempt_dir / "stderr.log").read_text(encoding="utf-8")
        self.assertIn("exceeded deadline timeout", stderr_content)

        record = json.loads((attempt_dir / "execution_record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["exit_status"], ExitStatus.TIMED_OUT.value)

    def test_attempt_immutability_and_sequential_incrementing(self):
        """Verify attempts are sequentially numbered and prior attempts are never overwritten."""
        run_dir = self.root / "exp_sequential"

        # Attempt 1: Fails (nonexistent executable)
        rec1 = self.supervisor.execute(
            executable=self.root / "missing",
            args=[],
            run_dir=run_dir,
            experiment_id="EXP_SEQ",
            seed=1,
        )
        self.assertEqual(rec1.attempt_number, 1)
        self.assertTrue(rec1.attempt_dir.endswith("attempt0001"))
        nonce1 = rec1.run_nonce

        # Attempt 2: Times out
        rec2 = self.supervisor.execute(
            executable=sys.executable,
            args=["-c", "import time; time.sleep(5)"],
            run_dir=run_dir,
            experiment_id="EXP_SEQ",
            seed=1,
            timeout_seconds=0.2,
        )
        self.assertEqual(rec2.attempt_number, 2)
        self.assertTrue(rec2.attempt_dir.endswith("attempt0002"))
        nonce2 = rec2.run_nonce

        # Attempt 3: Succeeds
        rec3 = self.supervisor.execute(
            executable=sys.executable,
            args=["-c", "print('success')"],
            run_dir=run_dir,
            experiment_id="EXP_SEQ",
            seed=1,
        )
        self.assertEqual(rec3.attempt_number, 3)
        self.assertTrue(rec3.attempt_dir.endswith("attempt0003"))
        nonce3 = rec3.run_nonce

        # Verify all 3 attempts exist simultaneously
        attempt1_dir = Path(rec1.attempt_dir)
        attempt2_dir = Path(rec2.attempt_dir)
        attempt3_dir = Path(rec3.attempt_dir)

        self.assertTrue(attempt1_dir.is_dir())
        self.assertTrue(attempt2_dir.is_dir())
        self.assertTrue(attempt3_dir.is_dir())

        # Verify attempt 1 remained untouched
        rec1_disk = json.loads((attempt1_dir / "execution_record.json").read_text(encoding="utf-8"))
        self.assertEqual(rec1_disk["run_nonce"], nonce1)
        self.assertEqual(rec1_disk["exit_status"], ExitStatus.FAILED.value)

        # Verify distinct nonces
        self.assertEqual(len({nonce1, nonce2, nonce3}), 3)

    def test_cryptographic_hash_integrity_and_input_audit(self):
        """Verify inputs and outputs are hashed accurately with cryptographic SHA-256."""
        run_dir = self.root / "exp_hashes"
        in_file = self.root / "input_data.csv"
        in_file.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
        expected_in_hash = file_sha256(in_file)

        receipt = self.supervisor.execute(
            executable=sys.executable,
            args=["-c", "print('reading data')"],
            run_dir=run_dir,
            experiment_id="EXP_HASH",
            seed=42,
            input_files=[in_file],
        )

        self.assertEqual(receipt.exit_status, ExitStatus.COMPLETED.value)
        self.assertTrue(receipt.inputs_unmodified)
        self.assertEqual(receipt.inputs_before[str(in_file)], expected_in_hash)
        self.assertEqual(receipt.inputs_after[str(in_file)], expected_in_hash)

        # Check output file hashes
        attempt_dir = Path(receipt.attempt_dir)
        for out_name, out_hash in receipt.outputs.items():
            out_path = attempt_dir / out_name
            self.assertTrue(out_path.is_file())
            self.assertEqual(file_sha256(out_path), out_hash)

    def test_input_mutation_detection(self):
        """Verify that modification of input files during execution is detected and fails audit."""
        run_dir = self.root / "exp_tamper"
        in_file = self.root / "immutable_input.csv"
        in_file.write_text("original,data\n", encoding="utf-8")

        # Adversarial command: alters input file in-place
        tamper_cmd = f"open(r'{in_file}', 'a').write('tampered_line\\n')"
        receipt = self.supervisor.execute(
            executable=sys.executable,
            args=["-c", tamper_cmd],
            run_dir=run_dir,
            experiment_id="EXP_TAMPER",
            seed=42,
            input_files=[in_file],
        )

        self.assertEqual(receipt.exit_status, ExitStatus.FAILED.value)
        self.assertFalse(receipt.inputs_unmodified)
        self.assertIn("AUDIT_ERROR: Input files mutated", receipt.error_message or "")
        self.assertNotEqual(receipt.inputs_before[str(in_file)], receipt.inputs_after[str(in_file)])

    def test_real_native_bpfeat_engine_execution(self):
        """Verify supervised execution of real native build/debug/bpfeat_engine binary."""
        binary_path = _project_root / "build/debug/bpfeat_engine"
        if not binary_path.exists():
            self.skipTest(f"bpfeat_engine binary not found at {binary_path}")

        run_dir = self.root / "exp_engine"
        events_file = self.root / "events.csv"
        events_file.write_text(
            "seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
            "10,0,1,5,2520377,0\n"
            "30,1000000000,1,6,2520377,3\n"
            "70,2000000000,2,7,149192,1\n",
            encoding="utf-8",
        )

        model_file = self.root / "model.weights"
        model_file.write_text(
            "schema=bpfeat.taobao.features.v2\n"
            "bias=0.2\n"
            "w0=0.4\n"
            "w1=-0.1\n"
            "w2=0.3\n"
            "w3=0.2\n"
            "w4=-0.4\n"
            "w5=0.1\n"
            "w6=0.01\n",
            encoding="utf-8",
        )

        receipt = self.supervisor.execute(
            executable=binary_path,
            args=[
                "--events", str(events_file),
                "--model", str(model_file),
                "--out-dir", "{out_dir}",
                "--mode", "fixed",
            ],
            run_dir=run_dir,
            experiment_id="EXP_ENGINE_TEST",
            seed=999,
            input_files=[events_file, model_file],
        )

        self.assertEqual(receipt.exit_status, ExitStatus.COMPLETED.value)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.inputs_unmodified)

        attempt_dir = Path(receipt.attempt_dir)
        pred_file = attempt_dir / "predictions_unlabeled.csv"
        receipt_file = attempt_dir / "engine_receipt.json"

        self.assertTrue(pred_file.is_file())
        self.assertTrue(receipt_file.is_file())

        with pred_file.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        self.assertEqual([int(r["seq"]) for r in rows], [10, 30, 70])
        for r in rows:
            score = float(r["score"])
            self.assertTrue(0.0 <= score <= 1.0)

        # Output inventory verification
        self.assertIn("predictions_unlabeled.csv", receipt.outputs)
        self.assertIn("engine_receipt.json", receipt.outputs)
        self.assertIn("batch_controller.csv", receipt.outputs)
        self.assertEqual(file_sha256(pred_file), receipt.outputs["predictions_unlabeled.csv"])

    def test_real_native_bpfeat_cache_tool_execution(self):
        """Verify supervised execution of real native build/debug/bpfeat_cache_tool binary."""
        binary_path = _project_root / "build/debug/bpfeat_cache_tool"
        if not binary_path.exists():
            self.skipTest(f"bpfeat_cache_tool binary not found at {binary_path}")

        run_dir = self.root / "exp_cache_tool"
        events_file = self.root / "events.csv"
        events_file.write_text(
            "seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
            "1,1000,10,100,500,0\n"
            "2,2000,10,101,500,1\n"
            "3,3000,10,102,500,2\n",
            encoding="utf-8",
        )

        receipt = self.supervisor.execute(
            executable=binary_path,
            args=[
                "--events", str(events_file),
                "--policy", "exact_fresh",
                "--alpha", "0.10",
            ],
            run_dir=run_dir,
            experiment_id="EXP_CACHE_TEST",
            seed=777,
            input_files=[events_file],
        )

        self.assertEqual(receipt.exit_status, ExitStatus.COMPLETED.value)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.inputs_unmodified)

        attempt_dir = Path(receipt.attempt_dir)
        stdout_text = (attempt_dir / "stdout.log").read_text(encoding="utf-8")
        self.assertIn('"conservation_valid": true', stdout_text)


if __name__ == "__main__":
    unittest.main()
