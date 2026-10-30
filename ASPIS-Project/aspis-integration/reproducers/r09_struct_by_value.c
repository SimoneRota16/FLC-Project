/* EDDI: structs passed by value (byval) and returned through sret.
 * master: segfault (the _dup function and its calls disagree on byval) */
#include "handlers.h"
typedef struct { double m[3][3]; } Mat3;
static Mat3 mul(Mat3 a, Mat3 b) {
    Mat3 r;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) {
            r.m[i][j] = 0;
            for (int k = 0; k < 3; k++)
                r.m[i][j] += a.m[i][k] * b.m[k][j];
        }
    return r;
}
int main(void) {
    Mat3 a = {{{1, 2, 0}, {0, 2, 0}, {0, 1, 3}}};
    Mat3 r = mul(a, a);
    printf("%.1f\n", r.m[0][0] + r.m[1][1] + r.m[2][2]);
    return 0;
}
