#!/usr/bin/env bash
# cepheus (SM8150 / Adreno 640) GPU source staging for the ios-sweet XNU build.
#
# Stage scripts run in the XNU source root before the patch loop. The GPU tree
# arrives beside this script in <patches>/cepheus-gpu (assembled by the workflow
# from the pinned UniXNU-nabu checkout plus the cepheus board files).
#
# M1 is the CP-proof build: GMU power/firmware, SMMU, CP ring and the ZAP
# authentication, but no Metal publication (NativeAdrenoSubmit/Timer/UserClient/
# Client/Publish/Accelerator/Scheduler are intentionally not compiled yet).
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
src="$here/cepheus-gpu"
[[ -d "$src/a640" ]] || { echo "cepheus GPU sources missing: $src/a640" >&2; exit 1; }
[[ -f iokit/conf/files ]] || { echo 'not an XNU source root' >&2; exit 1; }

dst=iokit/Kernel/Adreno
mkdir -p "$dst"

# Upstream first, then the A640 overlay: same-named overlay files replace the
# generic Adreno6xx files (the nabu build does the same at build time).
cp -R "$src/upstream/Adreno6xx/." "$dst"/
cp -R "$src/a640/." "$dst"/
cp -R "$src/upstream/ArmSmmu4K/." "$dst"/
cp -R "$src/upstream/AdrenoPM4/." "$dst"/
cp "$src/board/CepheusGpuResources.cpp" "$src/board/CepheusGpuFirmware.h" \
   "$src/board/CepheusGpuBuild.h" "$dst"/
cp "$src/board/CepheusGpuStart.c" bsd/dev/cepheus_gpu_start.c

append() {
    local file=$1
    local line=$2
    grep -qF "$line" "$file" 2>/dev/null || printf '%s\n' "$line" >> "$file"
}

# CP-proof units (nabu build-nabu-adreno.py CPP tuple).
for n in NativeAdrenoMemory NativeAdrenoVm NativeAdrenoCpu NativeAdrenoKernelTime \
         NativeAdrenoRing NativeAdrenoCpInit NativeAdrenoIrq NativeAdrenoSmmuMemory \
         NativeAdrenoSmmuContext NativeAdrenoGmuMemory NativeAdrenoGmuContext \
         NativeAdrenoGpuContext NativeAdrenoA6xxPower NativeAdrenoA6xxGmu \
         NativeAdrenoA6xxHwInit NativeAdrenoA6xxSmmu NativeAdrenoA6xxZap \
         NativeAdrenoService NativeAdrenoSha256 NativeAdrenoGpuProfile \
         CepheusGpuResources; do
    append iokit/conf/files "iokit/Kernel/Adreno/$n.cpp	optional iokitcpp"
done

for n in ArmSmmu4K ArmSmmu4KAudit ArmSmmu4KContext ArmSmmu4KLive ArmSmmu4KMmio \
         ArmSmmu4KProgram ArmSmmu4KStreams ArmSmmu4KTableMemory AdrenoPM4; do
    append iokit/conf/files "iokit/Kernel/Adreno/$n.c	standard"
done

append bsd/conf/files "bsd/dev/cepheus_gpu_start.c	standard"

echo "cepheus GPU staged: $(find "$dst" -maxdepth 1 -type f | wc -l) files in $dst"
