/* CFCSS/RASM/RACFED: longjmp back to a setjmp.
 * master: false signature mismatch after the second return of setjmp */
#include <setjmp.h>
#include "handlers.h"
static jmp_buf env;
static void fail(int depth) {
    if (depth == 0)
        longjmp(env, 1);
    fail(depth - 1);
}
int main(void) {
    if (setjmp(env) == 0) {
        fail(3);
        printf("not reached\n");
    } else {
        printf("recovered\n");
    }
    return 0;
}
