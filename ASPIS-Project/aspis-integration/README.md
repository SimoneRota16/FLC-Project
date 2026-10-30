# Integration into ASPIS

What is needed to merge the work of the project into the ASPIS main branch
(`HEAPLab/ASPIS`, base commit `b66a090`). The patches have not been
submitted yet.

| Path | Content |
|---|---|
| `patches/` | 4 commits for ASPIS, produced with `git format-patch` |
| `flc_tests.toml` | the `[[tests]]` entries of the four applications, as appended to `testing/config/tests.toml` by patch 0004 |
| `reproducers/` | minimal programs for the two EDDI bugs |

## The patches

| # | Commit | Bug |
|---|---|---|
| 0001 | fix(EDDI): null-safe consistency checks driven by the LLVM type of the values | checks that dereference a null pointer (`reproducers/null_pointer.c`) |
| 0002 | fix(EDDI): re-synchronise the duplicated memory after calls to non-duplicated functions | crash of all four applications (`reproducers/string_literal.c`) |
| 0003 | fix(RASM, RACFED): check the signature in the verification blocks of EDDI | found by fault injection |
| 0004 | test: add the applications of the FLC 2026/27 project | |

Every commit builds on its own with LLVM 21.1.8. To apply them:

```bash
git clone --recursive https://github.com/HEAPLab/ASPIS && cd ASPIS
git checkout b66a090
git am <this dir>/patches/*.patch
```

## Regression tests

Patch 0004 copies the applications into `testing/tests/c/applications/` and
appends `flc_tests.toml` to `testing/config/tests.toml`. The official harness
then runs each of them with the 55 combinations of data protection and
control-flow checking, together with the existing tests:

```bash
cd testing && pytest test.py -v
```

With the four patches all the 220 builds of the applications pass, and the
existing tests give the same results as on `b66a090` (see
`../results/compatibility/`).
