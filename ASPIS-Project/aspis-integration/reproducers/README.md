# Reproducers

Minimal programs for the two EDDI bugs fixed by the first two patches. On
the main branch of ASPIS (`b66a090`) both crash when compiled with EDDI;
with the patches they print the same output as the unhardened program.

| Program | Bug | Fixed by |
|---|---|---|
| `null_pointer.c` | a consistency check dereferences a null pointer (`realloc(NULL, n)`) | `0001` |
| `string_literal.c` | the re-synchronisation after `printf` writes into a string literal (`.rodata`) | `0002` |

```bash
cd /tmp && <ASPIS>/aspis.sh --llvm-bin <llvm>/bin --eddi --no-cfc \
    <this dir>/string_literal.c -o prog && ./prog
# main branch: Segmentation fault; with the patches: hello
```

`handlers.h` defines the two fault handlers that ASPIS calls on a detection.
