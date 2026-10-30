/* REDDI: a to_harden function returning a value.
 * master: the calls go to its _ret version, which is not hardened; the code
 * duplicated on demand there (the call to the to_duplicate function) reads the
 * never-written copy of a local variable: false data corruption */
#include "handlers.h"
__attribute__((annotate("to_harden"))) int g = 1200;
__attribute__((annotate("to_duplicate"))) static int scale(int raw, int num, int den) {
    return raw * num / den;
}
__attribute__((annotate("to_harden"))) static int step(int measure) {
    return g - scale(measure, 3, 2);
}
int main(void) {
    int m = 300;
    for (int k = 0; k < 20; k++)
        m += step(m) / 4;
    printf("%d\n", m);
    return 0;
}
