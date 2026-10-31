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
| `benchmarks/` | the four self-checking applications: AES-128, FFT, Huffman coding, PID controller |
| `aspis-integration/` | the fix of RASM and the test entries as two patches for ASPIS, the bug report of EDDI and its reproducer |
| `fault_injection/gdb_inject.py` | one fault-injection experiment, run inside gdb (register bit-flip or inverted branch) |
| `fault_injection/campaign.py`, `campaign.toml` | the fault-injection campaign (builds, golden runs with valgrind, experiments with gdb, results) |
| `fault_injection/analyze.py` | tables and figures of the report |
| `fault_injection/sdc_sites.py`, `check_jumps.py` | where the SDCs happened; share of the executed jumps that belong to the checks |
| `results/` | logs of the ASPIS harness and results of the campaign |
| `report/` | the report and the script that builds it |

## Reproducing the experiments

Requirements: Linux x86-64, LLVM 21.1.8, CMake, Ninja, gdb, valgrind,
Python 3.11+ with `pytest`, `pytest-timeout` and `matplotlib`; pandoc and
Node.js with Playwright to rebuild the PDF. The commands are in Appendix A of the report.

## License

The applications and the scripts are released under the MIT
license (see the SPDX headers), so that they can be included in ASPIS.
