# Integration into ASPIS

What is needed to merge the work of the project into the ASPIS main branch
(`HEAPLab/ASPIS`, base commit `b66a090`). Nothing has been submitted yet.

| Path | Content |
|---|---|
| `patches/` | 2 commits for ASPIS, produced with `git format-patch` |
| `flc_tests.toml` | the `[[tests]]` entries of the four applications, as appended to `testing/config/tests.toml` by patch 0002 |
| `bug_report.md` | the EDDI bug we found (crash after a library call that receives a pointer to a string literal), ready to be opened as an issue |
| `reproducers/` | the five-line program that reproduces it |

## The patches

| # | Commit |
|---|---|
| 0001 | fix(RASM, RACFED): check the signature in the verification blocks of EDDI (found by fault injection) |
| 0002 | test: add the applications of the FLC 2026/27 project |

Each commit builds on its own with LLVM 21.1.8. To apply them:

```bash
git clone --recursive https://github.com/HEAPLab/ASPIS && cd ASPIS
git checkout b66a090
git am <this dir>/patches/*.patch
```

## Regression tests

Patch 0002 copies the applications into `testing/tests/c/applications/` and
appends `flc_tests.toml` to `testing/config/tests.toml`. The official harness
then runs each of them with the 55 combinations of data protection and
control-flow checking, together with the existing tests:

```bash
cd testing && pytest test.py -v
```

All the 220 builds of the applications pass, on `b66a090` as well as with
the patches, and the existing tests give the same results with and without
patch 0001 (see `../results/compatibility/`).
