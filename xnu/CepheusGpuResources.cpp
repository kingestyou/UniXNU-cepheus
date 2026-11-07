/* SPDX-License-Identifier: MIT */
/* cepheus (Xiaomi Mi 9, SM8150 / Adreno 640) board facts for the A640 driver.
 *
 * Every window, SID and IRQ below is SM8150 silicon level and is shared with
 * nabu (Xiaomi Pad 5, same SoC). The cepheus Android FDT reports the same GPU
 * (0x02c00000), GMU (0x02c6a000), GPUCC (0x02c90000) and GPU SMMU (0x02ca0000)
 * windows, so the nabu table is used verbatim. Firmware is embedded at compile
 * time (see CepheusGpuFirmware.h) because this kernel boots from a payload and
 * has no ADT node for the GPU.
 */
#include "NativeAdrenoA6xxService.h"
#include "CepheusGpuFirmware.h"
#include "CepheusGpuBuild.h"
#include <IOKit/IOLib.h>
#include <string.h>

namespace {
struct PollSource { uint32_t number; void (*callback)(void *); void *context; bool enabled; };
PollSource sources[4]{};
unsigned sourceCount = 0;
} // namespace

extern "C" int native_adreno_a6xx_resources(NativeAdrenoA6xxResources *out)
{
    if (!out) {
        return 1;
    }
    *out = {};
    NativeAdrenoA6xxResources r{};

    r.gpu = {0x02c00000ULL, 0x40000ULL};
    r.gmu = {0x02c6a000ULL, 0x30000ULL};
    r.rscc = {0x02c8d000ULL, 0x2000ULL};
    r.smmu = {0x02ca0000ULL, 0x10000ULL};
    r.smmuTcu = {0x02cc2000ULL, 0x20ULL};
    r.smmuTbu[0] = {0x02cc5000ULL, 0x1000ULL};
    r.smmuTbu[1] = {0x02cc9000ULL, 0x1000ULL};
    r.smmuTbuStatus[0] = {0x02cc2200ULL, 8ULL};
    r.smmuTbuStatus[1] = {0x02cc2208ULL, 8ULL};
    r.gpucc = {0x02c90000ULL, 0x9000ULL};
    r.gcc = {0x00100000ULL, 0x1f0000ULL};
    r.pdc = {0x0b290000ULL, 0x10000ULL};
    r.pdcSeq = {0x0b490000ULL, 0x10000ULL};
    r.commandDb = {0x85f20000ULL, 0x20000ULL};
    r.rpmh = {0x18220000ULL, 0x10000ULL};
    r.aop = {0x0c300000ULL, 0x400ULL};
    r.aopDoorbell = {0x17c00000ULL, 0x1000ULL};
    r.zap = {0x98f15000ULL, 0x2000ULL};

    r.smmuTbuSidStart[0] = 0;
    r.smmuTbuSidCount[0] = 0x400;
    r.smmuTbuSidStart[1] = 0x400;
    r.smmuTbuSidCount[1] = 0x400;

    r.gpuInterrupt = 332;
    r.smmuGlobalInterrupt = 706;
    for (unsigned i = 0; i < 8; ++i) {
        r.smmuContextInterrupts[i] = 713 + i;
    }
    r.smmuContextInterruptCount = 8;

    r.chipId = 0x06040001;
    r.gmemBytes = 0x100000;
    r.frequencyHz = 257000000;
    r.highestBankBit = 15;
    r.minAccessLength = 32;
    r.ubwcMode = 3;

    r.gpuBank = 0;
    r.gpuAsid = 1;
    r.gpuSlot = 0;
    r.gpuSid = 0;
    r.gpuSidMask = 0x401;
    r.gmuBank = 1;
    r.gmuAsid = 2;
    r.gmuSlot = 4;
    r.gmuSid = 5;
    r.gmuSidMask = 0x400;

    r.aopDoorbellOffset = 0xc;
    r.aopDoorbellValue = 1;
    r.zapPasId = 13;

    r.gmuFirmware = cepheus_a640_gmu_data;
    r.gmuFirmwareBytes = sizeof(cepheus_a640_gmu_data);
    r.sqeFirmware = cepheus_a630_sqe_data;
    r.sqeFirmwareBytes = sizeof(cepheus_a630_sqe_data);
    r.zapMetadata = cepheus_a640_zap_metadata_data;
    r.zapMetadataBytes = sizeof(cepheus_a640_zap_metadata_data);
    r.zapShader = cepheus_a640_zap_shader_data;
    r.zapShaderBytes = sizeof(cepheus_a640_zap_shader_data);

    *out = r;
    IOLog("CepheusGPU: board %s gpu=%llx gmu=%llx gpucc=%llx smmu=%llx irq=%u/%u firmware=%lu/%lu/%lu/%lu\n",
        CEPHEUS_GPU_SOURCE_ID,
        r.gpu.physical, r.gmu.physical, r.gpucc.physical, r.smmu.physical,
        r.gpuInterrupt, r.smmuGlobalInterrupt,
        (unsigned long)r.gmuFirmwareBytes, (unsigned long)r.sqeFirmwareBytes,
        (unsigned long)r.zapMetadataBytes, (unsigned long)r.zapShaderBytes);
    return 0;
}

/* The cepheus kernel has no GIC SPI client API for these lines yet, so the
 * hardware worker polls the enabled callbacks (nabu model). Registration
 * accepts only the SM8150 GPU/SMMU interrupt numbers. */
extern "C" IOReturn native_adreno_smmu_register_irq(uint32_t number,
    void (*callback)(void *), void *context)
{
    if (!callback || !context || sourceCount >= 4 ||
        (number != 332 && number != 706 && (number < 713 || number > 720))) {
        return kIOReturnBadArgument;
    }
    for (unsigned i = 0; i < sourceCount; ++i) {
        if (sources[i].number == number) {
            return kIOReturnBusy;
        }
    }
    sources[sourceCount++] = {number, callback, context, false};
    return kIOReturnSuccess;
}

extern "C" IOReturn native_adreno_smmu_enable_irq(uint32_t number)
{
    for (auto &s : sources) {
        if (s.number == number && s.callback) {
            s.enabled = true;
            return kIOReturnSuccess;
        }
    }
    return kIOReturnNotFound;
}

extern "C" IOReturn native_adreno_smmu_disable_irq(uint32_t number)
{
    for (auto &s : sources) {
        if (s.number == number && s.callback) {
            s.enabled = false;
            return kIOReturnSuccess;
        }
    }
    return kIOReturnNotFound;
}

extern "C" void native_adreno_poll_irqs(void)
{
    for (auto &s : sources) {
        if (s.enabled && s.callback) {
            s.callback(s.context);
        }
    }
}

extern "C" int native_adreno_checkpoint(const char *phase)
{
    IOLog("CepheusGPU: checkpoint=%s\n", phase ? phase : "(null)");
    return 0;
}
