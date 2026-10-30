/* EDDI: a global initialised with the address of another global.
 * master: false data corruption (p_dup points to x instead of x_dup) */
#include "handlers.h"
int x = 1;
int *p = &x;
int main(void) {
    *p += 1;
    printf("%d\n", x);
    return 0;
}
