cmake_minimum_required(VERSION 3.16)
project(KLStream VERSION 3.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Compiler flags ────────────────────────────────────────────────────────────
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    add_compile_options(
        -Wall -Wextra -Wpedantic
        -O2
        -fno-omit-frame-pointer
    )
endif()

# ── Thread support ────────────────────────────────────────────────────────────
find_package(Threads REQUIRED)

# ── Interface library: klstream::klstream ─────────────────────────────────────
# Pure-header library; consuming targets just link this target and get the
# include path + pthread automatically — the exact CMake pattern described
# in the KLStream Implementation Guide Section 9.1.
add_library(klstream INTERFACE)
add_library(klstream::klstream ALIAS klstream)
target_include_directories(klstream INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(klstream INTERFACE Threads::Threads)
target_compile_features(klstream INTERFACE cxx_std_17)

# ── Sub-projects ──────────────────────────────────────────────────────────────
add_subdirectory(feature_flow)
add_subdirectory(tests)
