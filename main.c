#include <stdint.h>

#include "sieve.h"

int main(void) {
	uint8_t x = 0;
	
	for (;;) {
		x += 1;
		sieve();
	}

	return 0;
}
