# M1 GPU 构建 — 上传与运行

把以下文件放到 `kingestyou/UniXNU-cepheus`（保持路径）：

| 本地文件 | 仓库路径 | 说明 |
|---|---|---|
| `repo/.github/workflows/build-cepheus-gpu.yml` | `.github/workflows/build-cepheus-gpu.yml` | 新 workflow（kernel + firmware/bootimg） |
| `repo/scripts/build-kernel-patches.sh` | `scripts/build-kernel-patches.sh` | 替换原文件（增加 0086 + GPU 板级文件安装） |
| `repo/scripts/gen-cepheus-firmware.py` | `scripts/gen-cepheus-firmware.py` | 新文件（把 4 个固件嵌成头文件） |
| `repo/xnu/0086-stage-cepheus-gpu.sh` | `xnu/0086-stage-cepheus-gpu.sh` | 新文件（stage 脚本，拷贝驱动 + 追加编译列表） |
| `repo/xnu/CepheusGpuResources.cpp` | `xnu/CepheusGpuResources.cpp` | cepheus 板级资源表（SM8150） |
| `repo/xnu/CepheusGpuBuild.h` | `xnu/CepheusGpuBuild.h` | 构建标识 |
| `repo/xnu/CepheusGpuStart.c` | `xnu/CepheusGpuStart.c` | STARTUP_ARG 入口 |

注意：**不需要**上传 `CepheusGpuFirmware.h`（498 KB），workflow 会在构建时从
TheMuppets/cepheus vendor 拉固件并生成。

## 运行

1. GitHub → Actions → **build-cepheus-gpu** → Run workflow（master，`full`）
2. kernel job 会：
   - 拉取 pinned `zzweiqing/UniXNU-nabu`（A640 驱动）
   - 拉取 pinned `TheMuppets/proprietary_vendor_xiaomi_cepheus` 的 4 个固件
   - 生成嵌入头、staging 到 `iokit/Kernel/Adreno`
   - 编译 XNU
3. build job 沿用原 UEFI/payload/bootimg 流水线
4. 完成后下载 artifact `boot-cepheus.img`，把路径发我

## M1 验收（内核日志）

引导参数会由我加：`nabu-gpu=1 nabu-gpu-delay=30`（其余保持现有 cpus/quiet/keys/touch）。
预期日志顺序：

```
CepheusGPU: board cepheus-sm8150-a640 gpu=2c00000 gmu=2c6a000 gpucc=2c90000 smmu=2ca0000 ...
NativeAdrenoA6xx: A640 hardware start in 30 s
NativeAdrenoA6xx: hardware diagnostic worker started
NativeAdrenoA6xx: GPU CX GDSC inherited gdscr=... hw_ctrl=...
NativeAdrenoA6xx: ARC votes gpu=... gmu=...
NativeAdrenoA6xx: command-db ... (10 个资源)
NativeAdrenoA6xx: AOP QMP "..." status=0
NativeAdrenoA6xx: GMU ... firmware ... hfi ...
NativeAdrenoA6xx: CP init completed
NativeAdrenoCp: PAS shader startup completed status=0 ...
NativeAdrenoA6xx: step=7 status=0        ← CP proof ready
```

任何一步失败会打印 `power=... domain=... offset=... value=... expected=...` 或
`gmu=... hfi=... ack=...`，可以直接定位。

## 注意

- M1 是 **CP-proof**：跑通 GMU/CP/SMMU/ZAP，**不发布 Metal 设备**，所以界面仍然
  是软件渲染，不会有画面变化。
- `nabu-gpu` 没给或为 0 时，驱动完全不碰 GPU 寄存器。
- M2 再编译 Metal 发布路径（Submit/Timer/UserClient/Client/Publish/Accelerator/Scheduler）
  并处理 16.7.16 的沙箱授权。
