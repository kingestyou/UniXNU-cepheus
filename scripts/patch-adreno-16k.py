#!/usr/bin/env python3
"""Relax the A640 driver's native-4K page guard to also accept a native 16K kernel.

ios-sweet's SWEET platform builds XNU with 16K pages (__ARM_16K_PG__ 1), while
the nabu A640 driver was written for UniXNU's 4K kernel. The guard in
NativeAdrenoCpu.cpp only confirms that the kernel's CPU mappings are native
(matching granule, MMU on, valid TTBR1); the SMMU itself always builds 4K
stage-1 tables, which is independent of the CPU page size.

usage: patch-adreno-16k.py <NativeAdrenoCpu.cpp>
"""
import pathlib
import sys

OLD = """    bool native=PAGE_SIZE==4096 && out->kernel_page_bytes==4096 && out->kernel_map_page_bytes==4096 &&
        ((out->tcr>>14)&3)==0 && ((out->tcr>>30)&3)==2 &&
        (out->sctlr&1) && (out->ttbr1&UINT64_C(0x0000fffffffff000));
    return native?kIOReturnSuccess:kIOReturnUnsupported;"""

NEW = """    /* cepheus: ios-sweet builds a native 16K kernel. TCR.TG0/TG1 encode the
     * granule (TG1: 2=4K, 1=16K). The SMMU stage-1 tables stay 4K; the CPU
     * granule only has to be native and consistent with the kernel mappings. */
    const bool pages_4k=PAGE_SIZE==4096 && out->kernel_page_bytes==4096 &&
        out->kernel_map_page_bytes==4096 && ((out->tcr>>14)&3)==0 && ((out->tcr>>30)&3)==2;
    const bool pages_16k=PAGE_SIZE==16384 && out->kernel_page_bytes==16384 &&
        out->kernel_map_page_bytes==16384 && ((out->tcr>>14)&3)==1 && ((out->tcr>>30)&3)==1;
    bool native=(pages_4k||pages_16k) && (out->sctlr&1) &&
        (out->ttbr1&UINT64_C(0x0000fffffffff000));
    return native?kIOReturnSuccess:kIOReturnUnsupported;"""


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    p = pathlib.Path(sys.argv[1])
    text = p.read_text(encoding="utf-8")
    if NEW.splitlines()[2] in text and "pages_16k" in text:
        print("already patched:", p)
        return 0
    if OLD not in text:
        print("guard block not found in", p, file=sys.stderr)
        return 1
    p.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
