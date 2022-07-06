#include <stdint.h>

#include "mtb.h"
#include "sieve.h"

int main(void) {
	uint8_t x = 0;

	mtb_enable(4096);
	
	for (;;) {
		x += 1;
		sieve();
	}

	return 0;
}
