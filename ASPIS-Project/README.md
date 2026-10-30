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
| `aspis-integration/` | the fixes for ASPIS and the test entries as four patches, two minimal reproducers |
| `fault_injection/injector/fi.c` | ptrace-based fault injector for x86-64 Linux (register bit-flips, inverted branches) |
| `fault_injection/campaign.py`, `campaign.toml` | the fault-injection campaign (build, profile, inject, aggregate) |
| `fault_injection/analyze.py` | tables and figures of the report |
| `results/` | logs of the ASPIS harness and results of the campaign |
| `report/` | the report and the script that builds it |

## Reproducing the experiments

Requirements: Linux x86-64, LLVM 21.1.8, CMake, Ninja, Python 3.11+ with
`pytest`, `pytest-timeout` and `matplotlib`; pandoc and Node.js with
Playwright to rebuild the PDF. The commands are in Appendix A of the report.

## License

The applications, the injector and the scripts are released under the MIT
license (see the SPDX headers), so that they can be included in ASPIS.
