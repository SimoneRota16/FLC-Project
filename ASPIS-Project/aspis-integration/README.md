# Integration into ASPIS

This directory contains everything needed to merge the work of the project
into the ASPIS main branch (`HEAPLab/ASPIS`, base commit `b66a090`).

| Path | Content |
|---|---|
| `patches/aspis/` | 19 commits for ASPIS (`git format-patch`): 17 fixes/features of the passes and 2 commits for the regression tests |
| `patches/tda/` | 1 commit for the `TypeDeductionAnalysis` submodule (`NiccoloN/TypeDeductionAnalysis`, base `f9f6e44`) |
| `flc_tests.toml` | the `[[tests]]` entries of the 22 benchmarks, in the format of `testing/config/tests.toml` |
| `reproducers/` | a minimal C program for each bug, and `run.py` to build them with several ASPIS checkouts |

## The patch series

Every commit builds on its own (checked with LLVM 21.1.8) and the series
ends exactly in the version of ASPIS used for the fault-injection campaign.

| # | Commit | Reproducer |
|---|---|---|
| 1 | fix(TDA): bound the unrolling of recursive types | `r02` |
| 2 | fix(EDDI): null-safe consistency checks driven by the LLVM type of the values | `r03` |
| 3 | fix(EDDI): re-synchronise the duplicated memory after calls to non-duplicated functions | `r01` |
| 4 | fix(EDDI): pass the original function as callback to non-duplicated functions | `r04` |
| 5 | fix(EDDI): the duplicate of a global refers to the duplicated globals | `r05` |
| 6 | fix(EDDI): remap nested constant expressions to the duplicated globals | `r06` |
| 7 | fix(EDDI): duplicated memmove on shared memory | `r07` |
| 8 | fix(FuncRetToRef): return pointer of variadic functions | `r08` |
| 9 | fix(EDDI): duplication of calls with variadic and by-value arguments | `r09` |
| 10 | fix(EDDI): clone of variable-length allocas | `r10` |
| 11 | fix(EDDI): initialization check while the verification block is built | (`c_expr_vm`) |
| 12 | fix(EDDI): temporary duplicates of arguments are valid for one call | `r13` |
| 13 | fix(REDDI): harden the _ret version of to_harden functions | `r12` |
| 14 | fix(EDDI): duplicated local variables start with the content of the original ones | (`c_unions_bitfields`) |
| 15 | feat(CFC): support setjmp/longjmp in CFCSS, RASM, inter-RASM and RACFED | `r11` |
| 16 | feat(inter-RASM): functions entered from non-hardened code | `r14` |
| 17 | fix(RASM, RACFED): check the signature in the verification blocks of EDDI | (fault injection) |
| 18 | test: add the benchmarks of the FLC 2026/27 project | |
| 19 | test: enable inter-RASM on cpp_class, cpp_heap and cpp_template | |

Two of the bugs (11 and 14) depend on the order in which EDDI visits the
instructions or on the content of the stack, so they have no reliable
minimal reproducer: the benchmark in parentheses exposes them. Commit 17
makes no program fail: it was found by the fault-injection campaign, where
EDDI combined with RASM or RACFED missed wrong branches into the
verification blocks of EDDI.

## How to apply

The first commit moves the submodule pointer to the fixed version of
`TypeDeductionAnalysis`, which has to be merged there first:

```bash
# 1. in the TypeDeductionAnalysis repository
git am patches/tda/0001-*.patch
# 2. in ASPIS (after updating 0001 to the hash of the merged TDA commit)
git am patches/aspis/*.patch
```

To try the series without touching the TDA repository, apply the TDA patch
inside the submodule working tree and skip the first ASPIS patch:

```bash
git -C libs/TypeDeductionAnalysis am $PWD/patches/tda/0001-*.patch
git am patches/aspis/000[2-9]-*.patch patches/aspis/001*.patch
```

## Regression tests

Commit 18 copies the benchmarks into `testing/tests/c/applications/` and
`testing/tests/c/language_features/` and appends `flc_tests.toml` to
`testing/config/tests.toml`. The official harness runs each of them with the
55 combinations of data protection and control-flow checking:

```bash
cd testing && pytest test.py --no-header -v
```

`../scripts/run_aspis_harness.py` runs the same harness with one pytest
process per test, in parallel; `../scripts/aspis_matrix.py` builds the same
matrix with a hard time limit on every compilation and run (pytest-timeout
does not stop a hanging `opt`), and classifies the failures.

Results with LLVM 21.1.8 (see the report for the details):

| Suite | master `b66a090` | with the series |
|---|---|---|
| FLC benchmarks, 22 x 55 builds | 435 pass (36%); EDDI, sEDDI and FDSC: 0 / 660 | 1210 pass (100%) |
| ASPIS tests, 2640 builds (187 blacklisted) | 2453 pass | 2453 pass |
| ASPIS blacklisted combinations, inter-RASM/RACFED | 81 pass | 104 pass (cpp_class, cpp_heap, cpp_template fully pass with inter-RASM) |
| `tests.toml` of the series: 70 tests, 3850 builds (154 blacklisted) | | 3696 pass |

## Reproducers

```bash
python3 reproducers/run.py --llvm-bin <llvm>/bin \
    --aspis master=<ASPIS master> --aspis patched=<ASPIS + series>
```
