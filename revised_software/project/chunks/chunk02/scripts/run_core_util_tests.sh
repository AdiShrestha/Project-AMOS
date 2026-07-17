#!/bin/bash
set -euo pipefail

# Compile test program
g++ -std=c++17 -Wall -Wextra -Wpedantic \
    -I../../../../source/include \
    test_core_util.cpp -o test_core_util

# Run test program
./test_core_util

# Clean up
rm ./test_core_util
