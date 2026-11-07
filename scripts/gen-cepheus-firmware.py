#!/usr/bin/env python3
"""Embed the four A640 vendor blobs into a C header.

usage: gen-cepheus-firmware.py <firmware-dir> <output-header>
"""
import hashlib
import pathlib
import sys

FILES = [
    ("cepheus_a640_gmu_data", "a640_gmu.bin"),
    ("cepheus_a630_sqe_data", "a630_sqe.fw"),
    ("cepheus_a640_zap_metadata_data", "a640_zap.mdt"),
    ("cepheus_a640_zap_shader_data", "a640_zap.b02"),
]


def emit(name: str, path: pathlib.Path) -> str:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    lines = [f"/* {path.name}: {len(data)} bytes sha256 {digest} */",
             f"static const unsigned char {name}[] = {{"]
    row = []
    for b in data:
        row.append("0x%02x," % b)
        if len(row) == 16:
            lines.append("    " + " ".join(row))
            row = []
    if row:
        lines.append("    " + " ".join(row))
    lines.append("};")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    fw = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = ["/* SPDX-License-Identifier: MIT */",
             "/* Generated; do not edit. */",
             "#ifndef CEPHEUS_GPU_FIRMWARE_H",
             "#define CEPHEUS_GPU_FIRMWARE_H", ""]
    for name, filename in FILES:
        p = fw / filename
        if not p.is_file():
            print("missing firmware:", p, file=sys.stderr)
            return 1
        parts.append(emit(name, p))
        parts.append("")
    parts.append("#endif")
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("wrote", out, out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
