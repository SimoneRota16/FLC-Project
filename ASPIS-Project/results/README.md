# Results

All the experiments were run with LLVM 21.1.8 on x86-64 Linux (a 4-core
virtual machine), with ASPIS `b66a090` ("master") and with the same commit
plus the patches of `../aspis-integration/patches` ("fixed").

## `compatibility/`

Logs of the official ASPIS harness (`pytest test.py -v` in `testing/`, one
line per build: `test.py::test_aspis[<test>-<cfc>-<data>] PASSED`), gzipped:

| File | ASPIS | Tests |
|---|---|---|
| `harness_master.log.gz` | master | the 48 tests of `tests.toml` and our 4 applications |
| `harness_fixed.log.gz` | fixed (patches 0001-0004) | the same |

`../fault_injection/analyze.py --harness` turns them into the tables of
Section 3 of the report.

## `fault_injection/`

Output of `../fault_injection/campaign.py`, exported with `export.py`:

- `metrics.csv`: one row per application and configuration: size of
  `.text`, consistency checks inserted by EDDI, instructions executed in the
  program's own code in the golden run;
- `outcomes.csv`: one row per application, configuration and fault model:
  number of experiments per outcome, SDC rate with its 95% Wilson interval;
- `raw.csv.gz`: one row per experiment: application, configuration, chunk,
  then the columns printed by `fi inject` (`id`, `model`, `pc_off` offset of
  the target instruction in the text segment, `occurrence`, `target`
  register or condition code, `bit`, `injected`, `outcome`, `exit` status,
  `signal`, `time_us`);
- `before_fix/`: the same files for EDDI+RASM compiled with ASPIS without
  patch 0003 (bug 3 of the report).
