#!/bin/bash
set -euo pipefail

# Compile test program
g++ -std=c++17 -Wall -Wextra -Wpedantic \
    -I../../../../source/include \
    test_worker_scheduler.cpp -o test_worker_scheduler -lpthread

# Run test program
./test_worker_scheduler

# Clean up
rm ./test_worker_scheduler
