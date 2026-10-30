/* FuncRetToRef/EDDI: a variadic function returning a value.
 * master: broken module ("Call parameter type does not match function signature") */
#include <stdarg.h>
#include "handlers.h"
static int sum(int n, ...) {
    va_list ap;
    int s = 0;
    va_start(ap, n);
    for (int i = 0; i < n; i++)
        s += va_arg(ap, int);
    va_end(ap);
    return s;
}
int main(void) { printf("%d\n", sum(3, 1, 2, 3)); return 0; }
