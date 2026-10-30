# Harden a C application with ASPIS

Project of the course *Formal Languages and Compilers*, A.Y. 2026/27,
Politecnico di Milano. Students: Alberto Rotolo, Simone Rota. Supervisors:
Davide Baroffio, Emilio Corigliano.

The goals of the project were to protect C applications with
[ASPIS](https://github.com/HEAPLab/ASPIS), to verify the protection with
fault injection, and to integrate the applications into the ASPIS main branch
for regression testing. **The report is in [`report/report.pdf`](report/report.pdf)**
(sources in `report/report.md`).

## Contents

| Path | Content |
|---|---|
| `benchmarks/applications/` | 8 self-checking applications: AES-128, binary search tree, expression compiler + VM, FFT, Huffman coding, LU solver, PID controller, Sobel filter |
| `benchmarks/features/` | 14 microbenchmarks, each stressing a feature of C (callbacks, varargs, structs by value, VLAs, setjmp/longjmp, bit-fields, ...) |
| `aspis-integration/` | the fixes for ASPIS as a series of 18 commits (`patches/`), the test entries for `testing/config/tests.toml`, one minimal reproducer per bug |
| `fault_injection/injector/fi.c` | ptrace-based fault injector for x86-64 Linux (register bit-flips, inverted branches, wrong jump targets) |
| `fault_injection/campaign.py`, `campaign.toml` | the fault-injection campaign (build, profile, measure, inject, aggregate) |
| `fault_injection/analyze.py` | tables and figures of the report |
| `scripts/aspis_matrix.py` | builds a set of programs with the 11 x 5 combinations of ASPIS techniques and classifies the failures |
| `scripts/run_aspis_harness.py` | runs the official ASPIS pytest harness, one process per test, in parallel |
| `results/` | raw and aggregated results of every experiment |
| `report/` | the report and the script that builds it |

## Reproducing the experiments

Requirements: Linux x86-64 (kernel >= 5.13 for the hardware breakpoints of
the injector; it falls back to software breakpoints otherwise), LLVM 21.1.8,
CMake, Ninja, Python 3.11+ with `pytest`, `pytest-timeout` and `matplotlib`,
pandoc and Node.js with Playwright to rebuild the PDF.

```bash
# toolchain and ASPIS with the fixes
curl -LO https://github.com/llvm/llvm-project/releases/download/llvmorg-21.1.8/LLVM-21.1.8-Linux-X64.tar.xz
tar xf LLVM-21.1.8-Linux-X64.tar.xz
git clone --recursive https://github.com/HEAPLab/ASPIS && cd ASPIS && git checkout b66a090
git -C libs/TypeDeductionAnalysis am <this repo>/ASPIS-Project/aspis-integration/patches/tda/*.patch
git am <this repo>/ASPIS-Project/aspis-integration/patches/aspis/000[2-9]-*.patch \
       <this repo>/ASPIS-Project/aspis-integration/patches/aspis/001*.patch
cmake -B build -G Ninja -DLLVM_DIR=<llvm>/lib/cmake/llvm && cmake --build build
```

```bash
# compatibility matrix of the 22 benchmarks (tests copied into ASPIS by commit 17)
python3 scripts/aspis_matrix.py --aspis <ASPIS> --llvm-bin <llvm>/bin \
    --tests aspis-integration/flc_tests.toml --out matrix
```

```bash
# fault-injection campaign: edit the paths at the top of campaign.toml, then
gcc -O2 -o fi fault_injection/injector/fi.c
python3 fault_injection/campaign.py fault_injection/campaign.toml --jobs $(nproc)
python3 fault_injection/analyze.py --campaign <output> --out report \
    --matrix master=<matrix of master> --matrix patched=<matrix with the fixes>
python3 report/build.py
```

## License

The benchmarks, the injector and the scripts are released under the MIT
license (see the SPDX headers), so that they can be included in ASPIS.
