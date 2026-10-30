/* EDDI: two calls in different branches passing a global and a local pointer
 * (the temporary duplicate of the local is reused by the second call).
 * master: broken module ("Instruction does not dominate all uses") */
#include "handlers.h"
static int buf[2] = {3, 4};
static void sum(int *a, int *out) { *out = a[0] + a[1]; }
static int f(int c) {
    int r;
    if (c)
        sum(buf, &r);
    else
        sum(buf, &r);
    return r;
}
int main(void) { printf("%d\n", f(1)); return 0; }
