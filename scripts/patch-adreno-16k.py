#!/usr/bin/env python3
"""Adapt the A640 driver to ios-sweet's native 16K kernel and add diagnostics.

ios-sweet's SWEET platform builds XNU with 16K pages (__ARM_16K_PG__ 1), while
the nabu A640 driver was written for UniXNU's 4K kernel. This script:

  1. relaxes the native-4K guard in NativeAdrenoQueryCpu4K to accept a native
     16K configuration (the SMMU stage-1 tables stay 4K, which is independent
     of the CPU granule), and
  2. adds IOLog diagnostics to the guard and to every failure branch of
     NativeAdrenoMemory::allocate, so the next boot log names the exact check
     that refuses the allocation.

usage: patch-adreno-16k.py <NativeAdrenoCpu.cpp> <NativeAdrenoMemory.cpp>
"""
import pathlib
import sys

CPU_OLD = """    bool native=PAGE_SIZE==4096 && out->kernel_page_bytes==4096 && out->kernel_map_page_bytes==4096 &&
        ((out->tcr>>14)&3)==0 && ((out->tcr>>30)&3)==2 &&
        (out->sctlr&1) && (out->ttbr1&UINT64_C(0x0000fffffffff000));
    return native?kIOReturnSuccess:kIOReturnUnsupported;"""

CPU_NEW = """    /* cepheus: ios-sweet builds a native 16K kernel. TCR.TG0/TG1 encode the
     * granule (TG1: 2=4K, 1=16K). The SMMU stage-1 tables stay 4K; the CPU
     * granule only has to be native and consistent with the kernel mappings. */
    const bool pages_4k=PAGE_SIZE==4096 && out->kernel_page_bytes==4096 &&
        out->kernel_map_page_bytes==4096 && ((out->tcr>>14)&3)==0 && ((out->tcr>>30)&3)==2;
    const bool pages_16k=PAGE_SIZE==16384 && out->kernel_page_bytes==16384 &&
        out->kernel_map_page_bytes==16384 && ((out->tcr>>30)&3)==1 &&
        (((out->tcr>>14)&3)==1 || ((out->tcr>>14)&3)==2); /* EL0 may be 4K (iOS binaries) */
    bool native=(pages_4k||pages_16k) && (out->sctlr&1) &&
        (out->ttbr1&UINT64_C(0x0000fffffffff000));
    IOLog("NativeAdrenoCpu: guard PAGE=%lu page=%llu kmap=%llu tcr=%llx sctlr=%llx ttbr1=%llx 4k=%d 16k=%d native=%d\\n",
        (unsigned long)PAGE_SIZE,
        (unsigned long long)out->kernel_page_bytes,
        (unsigned long long)out->kernel_map_page_bytes,
        (unsigned long long)out->tcr,(unsigned long long)out->sctlr,
        (unsigned long long)out->ttbr1,(int)pages_4k,(int)pages_16k,(int)native);
    return native?kIOReturnSuccess:kIOReturnUnsupported;"""

MEM_EDITS = [
# 1. make sure IOLog is available
("#include <IOKit/IOBufferMemoryDescriptor.h>",
 "#include <IOKit/IOBufferMemoryDescriptor.h>\n#include <IOKit/IOLib.h>"),
# 2. guard query failure in allocate (unique context: noteBackingRequest follows)
("""    NativeAdrenoCpuState cpu{};
    IOReturn status=NativeAdrenoQueryCpu4K(&cpu);
    if(status) {
        return status;
    }
    noteBackingRequest(bytes,reuse_backing);""",
 """    NativeAdrenoCpuState cpu{};
    IOReturn status=NativeAdrenoQueryCpu4K(&cpu);
    if(status) {
        IOLog("NativeAdrenoMemory: allocate refused by cpu4k guard status=%08x bytes=%lu\\n",status,(unsigned long)bytes);
        return status;
    }
    noteBackingRequest(bytes,reuse_backing);"""),
# 3. descriptor creation failed
("""    if(!storage_.descriptor) {
        return kIOReturnNoMemory;
    }
    storage_.write_combined=write_combined;""",
 """    if(!storage_.descriptor) {
        IOLog("NativeAdrenoMemory: descriptor allocation failed bytes=%lu bits=%u contiguous=%d wc=%d\\n",
            (unsigned long)bytes,bits,(int)contiguous,(int)write_combined);
        return kIOReturnNoMemory;
    }
    storage_.write_combined=write_combined;"""),
# 4. prepare failed
("""        storage_.descriptor->release();
        storage_.descriptor=nullptr;
        return status;
    }
    storage_.prepared=true;""",
 """        storage_.descriptor->release();
        storage_.descriptor=nullptr;
        IOLog("NativeAdrenoMemory: descriptor prepare failed status=%08x bytes=%lu bits=%u\\n",
            status,(unsigned long)bytes,bits);
        return status;
    }
    storage_.prepared=true;"""),
# 5. mapping / length mismatch
("""    if(!storage_.mapping || ((uintptr_t)storage_.mapping&4095) || bytes>UINTPTR_MAX-(uintptr_t)storage_.mapping ||
        storage_.descriptor->getLength()!=bytes) {
        goto failed;
    }""",
 """    if(!storage_.mapping || ((uintptr_t)storage_.mapping&4095) || bytes>UINTPTR_MAX-(uintptr_t)storage_.mapping ||
        storage_.descriptor->getLength()!=bytes) {
        IOLog("NativeAdrenoMemory: mapping geometry refused map=%p len=%lu bytes=%lu\\n",
            (void *)storage_.mapping,(unsigned long)storage_.descriptor->getLength(),
            (unsigned long)bytes);
        goto failed;
    }"""),
# 6. per-4K physical span refused
("""            if(!physical || (physical&4095) || length<4096 || physical>=limit || 4096>limit-physical) {
                status=kIOReturnUnsupported;
                goto failed;
            }""",
 """            if(!physical || (physical&4095) || length<4096 || physical>=limit || 4096>limit-physical) {
                IOLog("NativeAdrenoMemory: span refused offset=%lu phys=%llx length=%lu limit=%llx\\n",
                    (unsigned long)offset,(unsigned long long)physical,
                    (unsigned long)length,(unsigned long long)limit);
                status=kIOReturnUnsupported;
                goto failed;
            }"""),
# 7. contiguity refused
("""            if(contiguous && offset && physical!=storage_.spans[0].physical+offset) {
                status=kIOReturnUnsupported;
                goto failed;
            }""",
 """            if(contiguous && offset && physical!=storage_.spans[0].physical+offset) {
                IOLog("NativeAdrenoMemory: contiguity refused offset=%lu phys=%llx first=%llx\\n",
                    (unsigned long)offset,(unsigned long long)physical,
                    (unsigned long long)storage_.spans[0].physical);
                status=kIOReturnUnsupported;
                goto failed;
            }"""),
]


def patch_cpu(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    if "pages_16k" in text:
        print("cpu already patched:", path)
        return 0
    if CPU_OLD not in text:
        print("cpu guard block not found in", path, file=sys.stderr)
        return 1
    if "#include <IOKit/IOLib.h>" not in text:
        anchor = '#include "NativeAdrenoMemory.h"'
        if anchor not in text:
            print("cpu include anchor not found in", path, file=sys.stderr)
            return 1
        text = text.replace(anchor, anchor + "\n#include <IOKit/IOLib.h>", 1)
    path.write_text(text.replace(CPU_OLD, CPU_NEW, 1), encoding="utf-8")
    print("patched", path)
    return 0


def patch_mem(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    if "NativeAdrenoMemory: allocate refused by cpu4k guard" in text:
        print("memory already patched:", path)
        return 0
    for index, (old, new) in enumerate(MEM_EDITS, 1):
        if old not in text:
            print(f"memory edit {index} not found in {path}", file=sys.stderr)
            return 1
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("patched", path)
    return 0


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    if patch_cpu(pathlib.Path(sys.argv[1])):
        return 1
    return patch_mem(pathlib.Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
