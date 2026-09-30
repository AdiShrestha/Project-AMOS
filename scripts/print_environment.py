#!/usr/bin/env python3
"""
print_environment.py - Print machine-readable environment summary for BPFeat.
"""

import json
import os
import platform
import subprocess
import sys

def get_version(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return res.stdout.strip().splitlines()[0] if res.returncode == 0 else "UNKNOWN"
    except Exception:
        return "NOT_FOUND"

def main():
    env_info = {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count() or 1
        },
        "python": {
            "version": sys.version.splitlines()[0],
            "executable": sys.executable
        },
        "tools": {
            "git": get_version(["git", "--version"]),
            "cmake": get_version(["cmake", "--version"]),
            "ctest": get_version(["ctest", "--version"]),
            "c_compiler": get_version(["cc", "--version"]),
            "cxx_compiler": get_version(["c++", "--version"])
        }
    }
    print(json.dumps(env_info, indent=2))

if __name__ == "__main__":
    main()
