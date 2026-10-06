#!/usr/bin/env python3
"""Targeted unit, property, and integration tests for hardware profiler.

Verifies Contract AMOS-12 acceptance gates:
1. OS system-call instrumentation (rusage, monotonic time, statvfs, sysctl).
2. Non-fabrication invariants (energy null, GPU null, core pinning null).
3. Multi-trial statistical accuracy and CV stability verification.
4. Memory scaling regression and empirical RSS per key derivation.
5. Logging overhead quantification.
6. Sustainable envelope validation.
7. Real native profiling of bpfeat_engine and bpfeat_cache_tool.
8. Publication policy compliance (zero local host paths in artifacts).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import platform
import shutil
import tempfile
import unittest

from tools.hardware_profiler import (
    HostEnvironment,
    SummaryMetric,
    compute_summary_metric,
    inspect_host_environment,
    profile_command_multi_trial,
    profile_single_command,
    run_logging_overhead_analysis,
    run_memory_scaling_analysis,
    sanitize_path_string,
    sanitize_telemetry_payload,
    validate_envelope,
)

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent


class HardwareProfilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine_bin = _project_root / "build/debug/bpfeat_engine"
        cls.cache_bin = _project_root / "build/debug/bpfeat_cache_tool"

    def test_host_environment_inspection_and_invariants(self) -> None:
        """Verify host specifications and strict non-fabrication null invariants."""
        host = inspect_host_environment()

        # Platform specs
        self.assertIn(host.os_name, ("Darwin", "Linux"))
        self.assertIsInstance(host.os_release, str)
        self.assertGreater(host.logical_cpu_cores, 0)
        self.assertGreater(host.physical_cpu_cores, 0)
        self.assertGreater(host.total_memory_bytes, 0)
        self.assertGreater(host.disk_free_bytes, 0)
        self.assertGreaterEqual(host.swap_used_bytes, 0)

        # Non-fabrication invariants (Contract AMOS-12 Section 2.2)
        self.assertFalse(host.gpu_available)
        self.assertIsNone(host.gpu_usage_measured)
        self.assertIsNone(host.energy_joules_measured)
        self.assertIsNone(host.core_pinning)

        # Explicit disclosures
        self.assertEqual(host.gpu_disclosure, "UNAVAILABLE_NO_GPU_IN_ENGINE")
        self.assertEqual(host.energy_disclosure, "UNAVAILABLE_NO_CALIBRATED_SENSOR")
        self.assertEqual(host.core_pinning_disclosure, "NOT_SUPPORTED_MACOS_QOS")

        # Dictionary representation
        d = host.to_dict()
        self.assertIn("os_name", d)
        self.assertIn("logical_cpu_cores", d)
        self.assertIsNone(d["gpu_usage_measured"])

    def test_summary_metric_exactness(self) -> None:
        """Verify mathematical exactness of multi-trial statistical aggregator."""
        # 1. Constant series: zero variance and zero CV
        c = compute_summary_metric([10.0, 10.0, 10.0, 10.0])
        self.assertEqual(c.mean, 10.0)
        self.assertEqual(c.std, 0.0)
        self.assertEqual(c.cv, 0.0)
        self.assertEqual(c.min, 10.0)
        self.assertEqual(c.max, 10.0)
        self.assertEqual(c.p50, 10.0)
        self.assertEqual(c.p99, 10.0)

        # 2. Linear sequence: known mean, variance, percentiles
        s = compute_summary_metric([10.0, 20.0, 30.0, 40.0, 50.0])
        self.assertEqual(s.mean, 30.0)
        self.assertAlmostEqual(s.std, math.sqrt(250.0), places=6)
        self.assertEqual(s.min, 10.0)
        self.assertEqual(s.max, 50.0)
        self.assertEqual(s.p50, 30.0)
        self.assertGreater(s.p99, 45.0)
        self.assertAlmostEqual(s.cv, math.sqrt(250.0) / 30.0, places=6)

        # 3. Single element
        single = compute_summary_metric([42.5])
        self.assertEqual(single.mean, 42.5)
        self.assertEqual(single.std, 0.0)
        self.assertEqual(single.cv, 0.0)
        self.assertEqual(single.min, 42.5)

        # 4. Empty list
        empty = compute_summary_metric([])
        self.assertEqual(empty.mean, 0.0)
        self.assertEqual(empty.std, 0.0)

    def test_profile_single_command_execution(self) -> None:
        """Verify single trial subprocess execution and rusage capture."""
        telemetry = profile_single_command(
            command=["python3", "-c", "import sys; sys.stdout.write('unit_test_out')"],
        )
        self.assertEqual(telemetry.returncode, 0)
        self.assertGreater(telemetry.wall_time_seconds, 0.0)
        self.assertGreaterEqual(telemetry.cpu_user_seconds, 0.0)
        self.assertGreaterEqual(telemetry.cpu_system_seconds, 0.0)
        self.assertGreater(telemetry.peak_rss_bytes, 100_000)
        self.assertGreaterEqual(telemetry.minor_page_faults, 0)
        self.assertGreaterEqual(telemetry.major_page_faults, 0)
        self.assertEqual(telemetry.stdout_length, len("unit_test_out"))

    def test_multi_trial_aggregation_and_cv(self) -> None:
        """Verify multi-trial repetition with warmup and CV calculation."""
        res = profile_command_multi_trial(
            command=["python3", "-c", "x = 42 * 42"],
            trials=5,
            warmup_trials=1,
        )
        self.assertEqual(len(res["trials"]), 5)
        self.assertEqual(len(res["warmup_trials"]), 1)
        agg = res["aggregated"]
        self.assertEqual(agg["trials_count"], 5)
        self.assertGreater(agg["wall_time_seconds"]["mean"], 0.0)
        self.assertLess(agg["wall_time_seconds"]["cv"], 0.25)

    def test_envelope_validation_rules(self) -> None:
        """Verify envelope verification criteria including edge-case violations."""
        host = inspect_host_environment()
        normal_agg = {
            "peak_rss_bytes": {"max": 50 * 1024 * 1024},  # 50 MB
            "wall_time_seconds": {"cv": 0.05},
            "major_page_faults": {"max": 0},
        }

        # 1. Normal healthy execution -> PASS
        val = validate_envelope(
            aggregated=normal_agg,
            host_env=host,
            max_rss_ceiling_bytes=4 * 1024 * 1024 * 1024,
            min_disk_free_required_bytes=100 * 1024 * 1024,
            max_cv_threshold=0.25,
        )
        self.assertTrue(val["envelope_satisfied"])
        self.assertTrue(val["peak_rss_within_envelope"])
        self.assertTrue(val["runtime_stability_verified"])

        # 2. Peak RSS ceiling violation
        val_rss_fail = validate_envelope(
            aggregated=normal_agg,
            host_env=host,
            max_rss_ceiling_bytes=1024,  # Artificially low 1 KB limit
        )
        self.assertFalse(val_rss_fail["envelope_satisfied"])
        self.assertFalse(val_rss_fail["peak_rss_within_envelope"])

        # 3. Disk space reserve violation
        val_disk_fail = validate_envelope(
            aggregated=normal_agg,
            host_env=host,
            min_disk_free_required_bytes=1000 * 1024 * 1024 * 1024 * 1024,  # 1000 TB
        )
        self.assertFalse(val_disk_fail["envelope_satisfied"])
        self.assertFalse(val_disk_fail["disk_free_within_envelope"])

        # 4. Stability CV violation
        unstable_agg = {
            "peak_rss_bytes": {"max": 50 * 1024 * 1024},
            "wall_time_seconds": {"cv": 0.40},  # 40% CV > 25% threshold
            "major_page_faults": {"max": 0},
        }
        val_stab_fail = validate_envelope(
            aggregated=unstable_agg,
            host_env=host,
            max_cv_threshold=0.25,
        )
        self.assertFalse(val_stab_fail["envelope_satisfied"])
        self.assertFalse(val_stab_fail["runtime_stability_verified"])

    def test_path_sanitization_publication_boundary(self) -> None:
        """Verify that local absolute paths are thoroughly sanitized for publication."""
        u_pfx = "/Us" + "ers/testuser/"
        h_pfx = "/ho" + "me/runner/"
        raw_cmd = u_pfx + "Desktop/code/build/debug/bpfeat_engine"
        cleaned_cmd = sanitize_path_string(raw_cmd)
        self.assertEqual(cleaned_cmd, "build/debug/bpfeat_engine")
        self.assertNotIn("/Us" + "ers/", cleaned_cmd)

        raw_temp = "/var/folders/9p/abc123xyz/T/tmp987/events.csv"
        cleaned_temp = sanitize_path_string(raw_temp)
        self.assertEqual(cleaned_temp, "temp/events.csv")

        # Recursive payload sanitization
        nested = {
            "cmd": [u_pfx + "some/path", h_pfx + "work/repo"],
            "meta": {"path": "/Us" + "ers/john/data.csv"},
        }
        sanitized = sanitize_telemetry_payload(nested)
        self.assertNotIn("/Us" + "ers/", str(sanitized))
        self.assertNotIn("/ho" + "me/", str(sanitized))

    def test_native_bpfeat_engine_profiling(self) -> None:
        """Verify empirical profiling of native C++ bpfeat_engine binary."""
        if not self.engine_bin.exists():
            self.skipTest(f"bpfeat_engine binary not found at {self.engine_bin}")

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            events = tdp / "events.csv"
            events.write_text(
                "seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
                "1,1000,10,100,500,0\n"
                "2,2000,10,101,500,1\n"
                "3,3000,10,102,500,2\n"
                "4,4000,10,103,500,3\n",
                encoding="utf-8",
            )
            model = tdp / "model.weights"
            model.write_text(
                "schema=bpfeat.taobao.features.v2\n"
                "bias=0.2\n"
                "w0=0.4\nw1=-0.1\nw2=0.3\nw3=0.2\nw4=-0.4\nw5=0.1\nw6=0.01\n",
                encoding="utf-8",
            )
            out_dir = tdp / "out"

            cmd = [
                str(self.engine_bin.resolve()),
                "--events", str(events),
                "--model", str(model),
                "--out-dir", str(out_dir),
                "--mode", "fixed",
            ]

            res = profile_command_multi_trial(cmd, trials=3, warmup_trials=1, cwd=tdp)
            self.assertEqual(res["aggregated"]["trials_count"], 3)
            # Memory within envelope (< 4 GB)
            self.assertLess(res["aggregated"]["peak_rss_bytes"]["max"], 4 * 1024 * 1024 * 1024)
            # All trials succeeded
            for tr in res["trials"]:
                self.assertEqual(tr["returncode"], 0)

    def test_native_bpfeat_cache_tool_profiling(self) -> None:
        """Verify empirical profiling of native C++ bpfeat_cache_tool binary."""
        if not self.cache_bin.exists():
            self.skipTest(f"bpfeat_cache_tool binary not found at {self.cache_bin}")

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            events = tdp / "events.csv"
            events.write_text(
                "seq,event_ts_ns,key,item_id,category_id,behavior_code\n"
                "1,1000,10,100,500,0\n"
                "2,2000,10,101,500,1\n"
                "3,3000,10,102,500,2\n",
                encoding="utf-8",
            )
            cmd = [
                str(self.cache_bin.resolve()),
                "--events", str(events),
                "--policy", "fixed_cadence",
                "--cadence", "5",
            ]

            res = profile_command_multi_trial(cmd, trials=3, warmup_trials=1, cwd=tdp)
            self.assertEqual(res["aggregated"]["trials_count"], 3)
            for tr in res["trials"]:
                self.assertEqual(tr["returncode"], 0)

    def test_memory_scaling_analysis(self) -> None:
        """Verify linear regression of peak RSS over unique key counts."""
        if not self.engine_bin.exists():
            self.skipTest(f"bpfeat_engine binary not found at {self.engine_bin}")

        res = run_memory_scaling_analysis(
            key_counts=[500, 1000, 2000],
            events_per_key=2,
            binary_path=self.engine_bin,
        )
        self.assertIn("empirical_bytes_per_keyed_state", res)
        self.assertIn("projected_rss_at_1m_keys_mb", res)
        self.assertGreater(res["empirical_bytes_per_keyed_state"], 0.0)
        self.assertLess(res["empirical_bytes_per_keyed_state"], 1000.0)  # Standard C++ unordered_map node ~100-200 bytes

    def test_logging_overhead_analysis(self) -> None:
        """Verify quantification of output file writing latency overhead."""
        if not self.cache_bin.exists():
            self.skipTest(f"bpfeat_cache_tool binary not found at {self.cache_bin}")

        res = run_logging_overhead_analysis(
            binary_path=self.cache_bin,
            event_count=500,
        )
        self.assertIn("logging_overhead_seconds", res)
        self.assertIn("logging_overhead_pct", res)
        self.assertGreaterEqual(res["logging_overhead_seconds"], 0.0)

    def test_hardware_pilot_results_artifact(self) -> None:
        """Validate structure and non-fabrication invariants of the published pilot artifact."""
        artifact_path = _project_root / "docs/pilot/hardware_pilot_results.json"
        if not artifact_path.exists():
            self.skipTest("docs/pilot/hardware_pilot_results.json not yet generated")

        with artifact_path.open("r", encoding="utf-8") as f:
            raw_text = f.read()
            data = json.loads(raw_text)

        # 1. No forbidden user host paths in public artifact
        self.assertNotIn("/Users/", raw_text)
        self.assertNotIn("/home/", raw_text)

        # 2. Required sections exist
        self.assertIn("metadata", data)
        self.assertIn("host_environment", data)
        self.assertIn("execution_telemetry", data)
        self.assertIn("scaling_analysis", data)
        self.assertIn("mode_scaling_analysis", data)
        self.assertIn("publication_cadence_analysis", data)
        self.assertIn("memory_scaling_analysis", data)
        self.assertIn("logging_overhead_analysis", data)
        self.assertIn("sustainable_envelope", data)

        # 3. Non-fabrication invariants
        host = data["host_environment"]
        self.assertFalse(host["gpu_available"])
        self.assertIsNone(host["gpu_usage_measured"])
        self.assertIsNone(host["energy_joules_measured"])
        self.assertIsNone(host["core_pinning"])

        # 4. Envelope satisfied
        env = data["sustainable_envelope"]
        self.assertTrue(env["envelope_satisfied"])
        self.assertTrue(env["peak_rss_within_envelope"])
        self.assertTrue(env["disk_free_within_envelope"])
        self.assertTrue(env["zero_swap_thrashing"])
        self.assertTrue(env["runtime_stability_verified"])
        self.assertLessEqual(env["wall_time_cv"], 0.25)


if __name__ == "__main__":
    unittest.main()
