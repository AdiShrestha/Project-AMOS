cmake_minimum_required(VERSION 3.16)

# ── Minimal test runner (no external framework dependency) ───────────────────
# Each test file defines main() and uses simple assert-style macros. This
# mirrors Project 2's test discipline: tests are self-contained binaries
# that return 0 on pass, non-zero on fail. CTest drives them.

enable_testing()

function(add_bpfeat_test name source)
    add_executable(${name} ${source})
    target_link_libraries(${name} PRIVATE klstream::klstream)
    add_test(NAME ${name} COMMAND ${name})
endfunction()

add_bpfeat_test(test_bpfeat_controller        test_bpfeat_controller.cpp)
add_bpfeat_test(test_alpha_controller         test_alpha_controller.cpp)
add_bpfeat_test(test_keyed_feature_extract_op test_keyed_feature_extract_op.cpp)
add_bpfeat_test(test_scoring_flush_op         test_scoring_flush_op.cpp)
add_bpfeat_test(test_drift_adaptive_window_op test_drift_adaptive_window_op.cpp)
add_bpfeat_test(test_pipeline_integration     test_pipeline_integration.cpp)
add_bpfeat_test(test_ralf_window_op           test_ralf_window_op.cpp)
add_bpfeat_test(test_backpressure_publisher_op test_backpressure_publisher_op.cpp)
add_bpfeat_test(test_ablation_architectures   test_ablation_architectures.cpp)
