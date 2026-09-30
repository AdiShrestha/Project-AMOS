#!/usr/bin/env python3
"""
test_repo_policy.py - Comprehensive unit & fixture tests for repo_policy.py.

Contract: C01-06 (Repaired in C02-01 per fix_package.md)
Factory Version: 2.2.0
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, TOOLS_DIR)

import repo_policy

class TestRepoPolicy(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="bpfeat_policy_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def init_git_repo(self, path):
        subprocess.check_call(["git", "init", "-b", "main"], cwd=path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=path)
        subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=path)

    def test_01_valid_fixture_passes(self):
        """Test that a clean, valid repository structure produces 0 policy violations."""
        repo_path = os.path.join(self.temp_dir, "valid_repo")
        os.makedirs(os.path.join(repo_path, "source", "core"), exist_ok=True)
        os.makedirs(os.path.join(repo_path, "tests"), exist_ok=True)
        os.makedirs(os.path.join(repo_path, "data", "schemas"), exist_ok=True)

        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "source", "core", "main.cpp"), "w") as f:
            f.write("#include <iostream>\nint main() { return 0; }\n")

        with open(os.path.join(repo_path, "data", "schemas", "data.schema.json"), "w") as f:
            f.write("{\"type\": \"object\"}\n")

        # Create valid inventory using closed set A_CANONICAL_SOURCE
        inv_path = os.path.join(repo_path, "inventory.json")
        with open(inv_path, "w") as f:
            json.dump({
                "schema_version": "bpfeat.chunk01.inventory.v1",
                "files": [
                    {"path": "source/core/main.cpp", "disposition_class": "A_CANONICAL_SOURCE"},
                    {"path": "data/schemas/data.schema.json", "disposition_class": "D_FIXTURE"}
                ]
            }, f)

        subprocess.check_call(["git", "add", "."], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Initial valid commit"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path, inventory_path=inv_path)
        hard_violations = [f for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertEqual(len(hard_violations), 0, f"Expected 0 violations for valid repo, got: {hard_violations}")

    def test_02_planted_forbidden_tracked_path(self):
        """POLICY-001: Detects tracked factory/governance files in outer index."""
        repo_path = os.path.join(self.temp_dir, "forbidden_tracked")
        os.makedirs(os.path.join(repo_path, "factory"), exist_ok=True)
        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "factory", "secret_spec.md"), "w") as f:
            f.write("Factory internal data\n")

        subprocess.check_call(["git", "add", "factory/secret_spec.md"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add forbidden factory path"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-001", rule_ids)

    def test_03_planted_build_artifact_tracked(self):
        """POLICY-002: Detects tracked build cache / output in outer index."""
        repo_path = os.path.join(self.temp_dir, "build_tracked")
        os.makedirs(os.path.join(repo_path, "build"), exist_ok=True)
        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "build", "CMakeCache.txt"), "w") as f:
            f.write("CMAKE_BUILD_TYPE=Debug\n")

        subprocess.check_call(["git", "add", "build/CMakeCache.txt"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add build artifact"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-002", rule_ids)

    def test_04_planted_raw_generated_artifact_tracked(self):
        """POLICY-003: Detects tracked raw dataset outside allowlist."""
        repo_path = os.path.join(self.temp_dir, "raw_tracked")
        os.makedirs(os.path.join(repo_path, "data", "raw"), exist_ok=True)
        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "data", "raw", "dump.csv.gz"), "w") as f:
            f.write("raw gzip data\n")

        subprocess.check_call(["git", "add", "data/raw/dump.csv.gz"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add raw dump"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-003", rule_ids)

    def test_05_planted_oversized_file(self):
        """POLICY-004: Detects oversized file exceeding max limit."""
        repo_path = os.path.join(self.temp_dir, "oversized_file")
        os.makedirs(os.path.join(repo_path, "source"), exist_ok=True)
        self.init_git_repo(repo_path)

        large_file = os.path.join(repo_path, "source", "large.dat")
        with open(large_file, "wb") as f:
            f.write(b"x" * 200000)

        subprocess.check_call(["git", "add", "source/large.dat"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add large file"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path, max_size_bytes=100000)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-004", rule_ids)

    def test_06_planted_broken_symlink(self):
        """POLICY-005: Detects broken symlink."""
        repo_path = os.path.join(self.temp_dir, "broken_link")
        os.makedirs(os.path.join(repo_path, "docs"), exist_ok=True)
        self.init_git_repo(repo_path)

        link_path = os.path.join(repo_path, "docs", "link.md")
        os.symlink("nonexistent_target.md", link_path)

        subprocess.check_call(["git", "add", "docs/link.md"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add broken link"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-005", rule_ids)

    def test_07_planted_absolute_author_path(self):
        """POLICY-006: Detects author-local absolute path in release text."""
        repo_path = os.path.join(self.temp_dir, "author_path")
        os.makedirs(os.path.join(repo_path, "source"), exist_ok=True)
        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "source", "main.cpp"), "w") as f:
            f.write('// Hardcoded debug path: /Users/author/data/test.csv\n')

        subprocess.check_call(["git", "add", "source/main.cpp"], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add source with absolute path"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-006", rule_ids)

    def test_08_planted_duplicate_roots(self):
        """POLICY-007: Detects duplicate implementation roots."""
        repo_path = os.path.join(self.temp_dir, "duplicate_roots")
        os.makedirs(os.path.join(repo_path, "source", "include", "klstream"), exist_ok=True)
        os.makedirs(os.path.join(repo_path, "include", "klstream"), exist_ok=True)
        self.init_git_repo(repo_path)

        with open(os.path.join(repo_path, "source", "include", "klstream", "a.hpp"), "w") as f:
            f.write("#pragma once\n")
        with open(os.path.join(repo_path, "include", "klstream", "a.hpp"), "w") as f:
            f.write("#pragma once\n")

        subprocess.check_call(["git", "add", "."], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add duplicate roots"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-007", rule_ids)

    def test_09_planted_missing_or_malformed_release_manifest(self):
        """POLICY-008: Detects admitted release artifact missing or with malformed manifest."""
        repo_path = os.path.join(self.temp_dir, "missing_manifest")
        os.makedirs(os.path.join(repo_path, "artifacts", "release"), exist_ok=True)
        os.makedirs(os.path.join(repo_path, "artifacts", "manifests"), exist_ok=True)
        self.init_git_repo(repo_path)

        # 1. Missing manifest case
        with open(os.path.join(repo_path, "artifacts", "release", "summary_table.csv"), "w") as f:
            f.write("metric,val\n")
        subprocess.check_call(["git", "add", "."], cwd=repo_path)
        subprocess.check_call(["git", "commit", "-m", "Add unmanifested release artifact"], cwd=repo_path, stdout=subprocess.DEVNULL)

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-008", rule_ids)

        # 2. Malformed manifest case
        with open(os.path.join(repo_path, "artifacts", "manifests", "summary_table.csv.manifest.json"), "w") as f:
            f.write("invalid json {")

        findings = repo_policy.check_policy(repo_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-008", rule_ids)

    def test_10_planted_unresolved_or_invalid_inventory_disposition(self):
        """POLICY-009: Detects invalid disposition or UNRESOLVED in inventory."""
        repo_path = os.path.join(self.temp_dir, "unresolved_inv")
        os.makedirs(os.path.join(repo_path, "source"), exist_ok=True)
        self.init_git_repo(repo_path)

        inv_path = os.path.join(repo_path, "inventory.json")
        with open(inv_path, "w") as f:
            json.dump({
                "schema_version": "bpfeat.chunk01.inventory.v1",
                "files": [
                    {"path": "source/test.cpp", "disposition_class": "INVALID_CUSTOM_CLASS"}
                ]
            }, f)

        findings = repo_policy.check_policy(repo_path, inventory_path=inv_path)
        rule_ids = [f["rule_id"] for f in findings if f["severity"] == "HARD_VIOLATION"]
        self.assertIn("POLICY-009", rule_ids)

if __name__ == "__main__":
    unittest.main()
