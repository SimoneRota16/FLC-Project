# EDDI: crash after a library call that receives a pointer to a string literal

Bug report for ASPIS, ready to be opened as an issue on `HEAPLab/ASPIS` (not
submitted yet).

**Version**: ASPIS `b66a090`, LLVM 21.1.8, x86-64 Linux.

## Reproducer

`reproducers/string_literal.c`:

```c
#include "handlers.h"
static void show(const char *label) { printf("%s\n", label); }
int main(void) { show("hello"); return 0; }
```

```bash
aspis.sh --llvm-bin <llvm>/bin --eddi --no-cfc string_literal.c -o prog && ./prog
```

Expected: `hello`. Actual: `Segmentation fault`. The same happens with every
variant of EDDI, with sEDDI and with FDSC, whatever the control-flow
technique.

## Analysis

After a call to a function that has no `_dup` version (here `printf`), the
callee may have written through its pointer arguments, updating only the
original copy of the data. `EDDI::fixFuncValsPassedByReference`
(`passes/EDDI.cpp`) therefore re-synchronises the duplicate: for every operand
of the call that is an instruction with a duplicate, it loads a value of
pointer type from the original pointer and stores it through the duplicate
pointer.

When the argument points to a string literal, the original and the duplicate
are the same address in `.rodata` (here the two copies of the parameter
`label`), so the store writes into read-only memory and the program crashes.
Independently of this case, the copy is always 8 bytes (the size of a
pointer), whatever the pointed type: it overflows objects smaller than 8 bytes
and synchronises only the first 8 bytes of larger ones.

## How we found it

The four applications of our project crashed with EDDI, sEDDI and FDSC on
`b66a090`. With `gdb` the faulting instruction was always an 8-byte store
right after a call to `printf`, into the string printed by
`printf("%s", label)` (a label received as a parameter) or by
`printf("%s\n", ok ? "SUCCESS" : "FAIL")`.

## Workaround

Pass string literals to library functions only directly, as constants
(`printf("SUCCESS\n")`), never through a parameter or a `? :`. Our
applications are written this way, and with this change all the 55
combinations of the harness pass on `b66a090`.

## Possible fix

Skip the arguments that the callee cannot write through (`readonly`) and the
constant globals; copy the whole object when the original and the duplicate
are distinct variables of known size; otherwise copy as many bytes as the
pointed type, and only when the two copies of the pointer differ at run time.
