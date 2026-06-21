cmake_minimum_required(VERSION 3.16)

add_executable(feature_flow_main main.cpp)
target_link_libraries(feature_flow_main PRIVATE klstream::klstream)

add_executable(feature_flow_harness harness.cpp)
target_link_libraries(feature_flow_harness PRIVATE klstream::klstream)
