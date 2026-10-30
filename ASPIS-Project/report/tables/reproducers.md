| reproducer | options | master | patched |
|---|---|---|---|
| `r01_string_param.c` | `--eddi --no-cfc` | crash (SIGSEGV) | ok |
| `r02_linked_list.c` | `--eddi --no-cfc` | compiler hangs | ok |
| `r03_null_argument.c` | `--eddi --no-cfc` | crash (SIGSEGV) | ok |
| `r04_qsort_callback.c` | `--eddi --no-cfc` | crash (SIGSEGV) | ok |
| `r05_global_pointer_init.c` | `--eddi --no-cfc` | false DataCorruption | ok |
| `r06_matrix_constant_index.c` | `--eddi --no-cfc` | false DataCorruption | ok |
| `r07_memmove_heap.c` | `--eddi --no-cfc` | wrong output | ok |
| `r08_variadic.c` | `--eddi --no-cfc` | broken module (call signature) | ok |
| `r09_struct_by_value.c` | `--eddi --no-cfc` | crash (SIGSEGV) | ok |
| `r10_vla.c` | `--eddi --no-cfc` | broken module (dominance) | ok |
| `r11_setjmp.c` | `--no-dup --cfcss` | false SigMismatch | ok |
| `r12_reddi_return.c` | `--reddi --no-cfc` | false DataCorruption | ok |
| `r13_two_calls.c` | `--eddi --no-cfc` | broken module (dominance) | ok |
| `r14_inter_rasm_callback.c` | `--no-dup --inter-rasm` | false SigMismatch | ok |
