#include <saml21.h>
#include <string.h>

#include "mtb.h"

void mtb_enable(size_t size) {
	uint32_t mask;

	if ((size < 16) || (__builtin_popcount(size) != 1)) {
		/* MTB must be >= 16 bytes, and a power of 2 */
		for (;;);
	}
	mask = __builtin_ctz(size) - 4;

	memset((void*)MTB->BASE.reg, 0, size);

	MTB->POSITION.reg = 0
		| MTB_POSITION_POINTER(0);

	MTB->FLOW.reg = 0;

	MTB->MASTER.reg = 0
		| MTB_MASTER_EN
		| MTB_MASTER_MASK(mask);
}

void mtb_disable(void) {
	MTB->MASTER.reg &= ~MTB_MASTER_EN;
}
