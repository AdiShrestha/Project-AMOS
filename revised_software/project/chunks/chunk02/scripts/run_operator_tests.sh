#!/bin/bash
set -euo pipefail

# Compile test program
g++ -std=c++17 -Wall -Wextra -Wpedantic \
    -I../../../../source/include \
    test_operator.cpp -o test_operator

# Run test program
./test_operator

# Clean up
rm ./test_operator
