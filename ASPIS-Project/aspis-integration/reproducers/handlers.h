/* Fault handlers shared by the reproducers: ASPIS calls them on a detection. */
#include <stdio.h>
#include <stdlib.h>
void DataCorruption_Handler(void) { fprintf(stderr, "FAULT_DETECTED: DataCorruption\n"); exit(2); }
void SigMismatch_Handler(void) { fprintf(stderr, "FAULT_DETECTED: SigMismatch\n"); exit(3); }
