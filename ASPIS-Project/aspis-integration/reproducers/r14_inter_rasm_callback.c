/* inter-RASM: a function called back by libc (qsort).
 * master: false signature mismatch (the callback is entered with the
 * signatures of another function) */
#include "handlers.h"
static int cmp(const void *a, const void *b) { return *(const int *)a - *(const int *)b; }
int main(void) {
    int v[4] = {3, 1, 4, 2};
    qsort(v, 4, sizeof(int), cmp);
    printf("%d %d %d %d\n", v[0], v[1], v[2], v[3]);
    return 0;
}
