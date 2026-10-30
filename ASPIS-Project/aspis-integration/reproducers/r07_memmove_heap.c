/* EDDI: overlapping memmove on heap memory (not duplicated).
 * master: wrong output, the data are shifted twice */
#include <string.h>
#include "handlers.h"
int main(void) {
    int *a = malloc(6 * sizeof(int));
    for (int i = 0; i < 6; i++)
        a[i] = i;
    memmove(a + 1, a, 5 * sizeof(int));
    printf("%d %d %d %d %d %d\n", a[0], a[1], a[2], a[3], a[4], a[5]);
    free(a);
    return 0;
}
