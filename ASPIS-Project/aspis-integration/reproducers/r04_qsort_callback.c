/* EDDI: a comparator passed to qsort.
 * master: segfault (qsort calls the _dup comparator, which has 4 parameters) */
#include "handlers.h"
static int cmp(const void *a, const void *b) { return *(const int *)a - *(const int *)b; }
int main(void) {
    int v[5] = {4, 2, 5, 1, 3};
    qsort(v, 5, sizeof(int), cmp);
    printf("%d %d %d %d %d\n", v[0], v[1], v[2], v[3], v[4]);
    return 0;
}
