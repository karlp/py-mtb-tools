#include "sieve.h"

/* Eratosthenes sieve */

#define N 10

static char notprime[N+1];

void sieve(void) {
	int k;

	for (int y = 0; y <= N; y++) {
		notprime[y] = 0;
	}

	k=2;

	while(k <= N) {
		int t=2;

		while ((t * k) <= N) {
			notprime[t*k] = 1;
			t++;
		}

		k++;

		while ((k <= N) && (notprime[k]==1)) {
			k++;
		}
	}
}
