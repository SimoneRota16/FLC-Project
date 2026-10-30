/* EDDI: a string literal reaches printf through a parameter.
 * master: segfault (the pointee is "synchronised" by a store into .rodata) */
#include "handlers.h"
static void show(const char *label) { printf("%s\n", label); }
int main(void) { show("hello"); return 0; }
