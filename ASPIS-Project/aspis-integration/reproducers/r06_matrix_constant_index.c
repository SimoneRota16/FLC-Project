/* EDDI: element of a 2-D global array written with constant indices (nested
 * constant GEP) and read with variable ones.
 * master: false data corruption (the duplicated store writes the original
 * array, so the duplicate is never updated) */
#include "handlers.h"
static unsigned char m[4][4];
static int get(int i, int j) { return m[i][j]; }
int main(void) {
    m[2][3] = 7;
    printf("%d\n", get(2, 3));
    return 0;
}
