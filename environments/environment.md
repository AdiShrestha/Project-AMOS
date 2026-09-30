# BPFeat Environment Specification

**Factory Version:** 2.2.0  
**Contract:** C01-05 (Amended in C02-01 per fix_package.md)  
**Lock Status:** NOT YET FROZEN (Provisional development baseline)

## Toolchain Requirements & Compatibility

- **C++ Standard:** C++17 (`CMAKE_CXX_STANDARD 17` strict adherence required by runtime and tests)
- **C++ Compiler:** Apple Clang / Clang / GCC with C++17 and pthreads support (`Apple clang version 21.0.0`)
- **CMake Build Minimum:** 3.16.0 (Command-line `cmake -S . -B ...` configuration boundary)
- **CMake Presets Minimum:** 3.20.0 (`CMakePresets.json` version 2 preset schema boundary)
- **Observed Host Environment:** Darwin arm64 (macOS 25.6.0), Apple Clang 21.0.0, CMake 4.4.1, CTest 4.4.1, Python 3.12.8

## Python Dependencies (Provisional / Candidate Stack)

The following third-party dependencies are candidate requirements for data preprocessing, model training, and analysis:

- `numpy`
- `pandas`
- `scipy`
- `scikit-learn`
- `matplotlib`
- `joblib`
- `pyyaml`
- `tabulate`

*Note:* A fully pinned lock file (`requirements.lock`) will be generated and validated in subsequent environment freezing contracts prior to full experimental execution.
