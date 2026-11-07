/* SPDX-License-Identifier: MIT */
/* cepheus (SM8150 / Adreno 640) A640 diagnostic entry.
 * The hardware sequence itself only runs when nabu-gpu=1 is present, waits
 * for IOBSD, then waits nabu-gpu-delay seconds (default 20) before touching
 * the GPU. Nothing is programmed without that explicit boot argument. */
#include <kern/startup.h>
extern void native_adreno_a6xx_start(void);
static void cepheus_gpu_start(const void *argument)
{
    (void)argument;
    native_adreno_a6xx_start();
}
STARTUP_ARG(EARLY_BOOT, STARTUP_RANK_LAST, cepheus_gpu_start, 0);
