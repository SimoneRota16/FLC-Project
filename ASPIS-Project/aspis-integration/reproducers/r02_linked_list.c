/* EDDI: any recursive struct (here a linked list).
 * master: opt never terminates (the type deduction unrolls the type forever) */
#include "handlers.h"
struct node { int key; struct node *next; };
int main(void) {
    struct node c = {3, NULL}, b = {2, &c}, a = {1, &b};
    int s = 0;
    for (struct node *n = &a; n != NULL; n = n->next)
        s += n->key;
    printf("%d\n", s);
    return 0;
}
