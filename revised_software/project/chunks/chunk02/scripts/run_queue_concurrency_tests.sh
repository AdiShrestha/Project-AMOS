#!/bin/bash
set -euo pipefail

# Compile test program with ThreadSanitizer if supported, or standard flags
# ThreadSanitizer is extremely valuable for validating lock-free correctness
g++ -std=c++17 -Wall -Wextra -Wpedantic \
    -fsanitize=thread -g \
    -I../../../../source/include \
    test_queue_concurrency.cpp -o test_queue_concurrency -lpthread

# Run test program
./test_queue_concurrency

# Clean up
rm ./test_queue_concurrency
