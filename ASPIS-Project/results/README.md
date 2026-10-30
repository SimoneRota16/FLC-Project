# Results

All the experiments were run with LLVM 21.1.8 on x86-64 Linux (a 4-core
virtual machine), with ASPIS `b66a090` ("master") and with the same commit
plus the patch series of `../aspis-integration/patches` ("patched").

## `compatibility/`

Output of `../scripts/aspis_matrix.py`: one row per build, with the outcome
(`pass`, `compile-error`, `compile-hang`, `crash`, `false-detect`,
`mismatch`, `exit-code`, `run-hang`, `skipped`) and a detail.

| File | Programs | ASPIS |
|---|---|---|
| `flc_master.csv` | the 22 benchmarks, 55 combinations each | master |
| `flc_patched.csv` (`.md`: matrix view) | the 22 benchmarks | patched |
| `aspis_tests_master.csv` | the 48 tests of `testing/config/tests.toml` | master |
| `aspis_tests_patched.csv` | the 48 tests | patched |
| `aspis_blacklisted_*.csv` | the tests with a `black_list`, only `--inter-rasm` and `--racfed`, blacklist ignored | master / patched |
| `reproducers.md` | `../aspis-integration/reproducers/run.py` | both |

## `fault_injection/`

Output of `../fault_injection/campaign.py` (exported with `export.py`):

- `metrics.csv`: one row per application and configuration: size of
  `.text`, compilation time, consistency checks inserted, instructions
  executed in the program's code (`dyn_app`) and in total (`dyn_total`),
  distinct instructions executed, minimum and median run time of 31 runs
  (wall clock, including the start-up of the process);
- `outcomes.csv`: one row per application, configuration and fault model:
  number of experiments per outcome, SDC rate with its 95% Wilson interval,
  detection rate, crash+hang rate;
- `raw.csv.gz`: one row per experiment (240,900): application,
  configuration, chunk, then the columns printed by `fi inject` (`id`,
  `model`, `pc_off` offset of the target instruction in the text segment,
  `occurrence`, `target` register / condition code / jump target, `bit`,
  `injected`, `outcome`, `exit` status, `signal`, `time_us`).
