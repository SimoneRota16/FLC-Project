# Reproducer

`string_literal.c` reproduces the EDDI bug described in `../bug_report.md`:
on the main branch of ASPIS (`b66a090`) it crashes when compiled with EDDI,
sEDDI or FDSC, while it should print `hello`.

```bash
cd /tmp && <ASPIS>/aspis.sh --llvm-bin <llvm>/bin --eddi --no-cfc \
    <this dir>/string_literal.c -o prog && ./prog
```

`handlers.h` defines the two fault handlers that ASPIS calls on a detection.
