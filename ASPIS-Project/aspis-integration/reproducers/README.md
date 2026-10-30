# Reproducers

One minimal program per bug found in ASPIS (`b66a090`). `run.py` compiles
each one with the options that expose the bug, using one or more ASPIS
checkouts, and compares the result with the program compiled without ASPIS:

```bash
python3 run.py --llvm-bin <llvm>/bin --aspis master=<dir> --aspis patched=<dir>
```

The expected result on master is written in the comment at the top of each
file; with the patch series every reproducer prints the same output as the
unhardened program.
