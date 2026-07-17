#!/bin/bash
set -euo pipefail

# Compile test program
g++ -std=c++17 -Wall -Wextra -Wpedantic \
    -I../../../../source/include \
    test_exact_count_termination.cpp -o test_exact_count_termination -lpthread

# Run test program
./test_exact_count_termination

# Clean up
rm ./test_exact_count_termination
