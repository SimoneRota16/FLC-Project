/* EDDI: a variable-length array.
 * master: broken module ("Instruction does not dominate all uses") */
#include "handlers.h"
static int f(int n) {
    int v[n];
    for (int i = 0; i < n; i++)
        v[i] = i * i;
    return v[n - 1];
}
int main(void) { printf("%d\n", f(5)); return 0; }
