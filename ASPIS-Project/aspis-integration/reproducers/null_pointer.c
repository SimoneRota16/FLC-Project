/* EDDI: a null pointer passed to a function (realloc(NULL, n) = malloc(n)).
 * master: segfault (the consistency check dereferences the null pointer) */
#include "handlers.h"
int main(void) {
    int *v = NULL;
    v = realloc(v, 4 * sizeof(int));
    v[0] = 42;
    printf("%d\n", v[0]);
    free(v);
    return 0;
}
