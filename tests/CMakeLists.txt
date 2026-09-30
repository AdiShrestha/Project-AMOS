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

add_bpfeat_test(test_bpfeat_controller        unit/test_bpfeat_controller.cpp)
add_bpfeat_test(test_alpha_controller         unit/test_alpha_controller.cpp)
add_bpfeat_test(test_keyed_feature_extract_op unit/test_keyed_feature_extract_op.cpp)
add_bpfeat_test(test_scoring_flush_op         unit/test_scoring_flush_op.cpp)
add_bpfeat_test(test_drift_adaptive_window_op unit/test_drift_adaptive_window_op.cpp)
add_bpfeat_test(test_pipeline_integration     integration/test_pipeline_integration.cpp)
add_bpfeat_test(test_ralf_window_op           unit/test_ralf_window_op.cpp)
add_bpfeat_test(test_backpressure_publisher_op unit/test_backpressure_publisher_op.cpp)
add_bpfeat_test(test_ablation_architectures   integration/test_ablation_architectures.cpp)
add_bpfeat_test(test_runtime_lifecycle         unit/test_runtime_lifecycle.cpp)
add_bpfeat_test(test_accounting_ledger         unit/test_accounting_ledger.cpp)
add_bpfeat_test(test_queue_lifecycle           unit/test_queue_lifecycle.cpp)
add_bpfeat_test(test_topology_manifest         unit/test_topology_manifest.cpp)
add_bpfeat_test(test_native_trace              unit/test_native_trace.cpp)
add_bpfeat_test(test_semantic_precision        unit/test_semantic_precision.cpp)
add_bpfeat_test(test_semantic_differential      unit/test_semantic_differential.cpp)
add_bpfeat_test(test_dataset_adapter            unit/test_dataset_adapter.cpp)
add_bpfeat_test(test_config_parser              unit/test_config_parser.cpp)
add_bpfeat_test(test_harness_registry           unit/test_harness_registry.cpp)
add_bpfeat_test(test_baseline_signatures        unit/test_baseline_signatures.cpp)
