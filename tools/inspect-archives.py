#!/usr/bin/env python3
"""Inspect PanProbe / Android diagnostic ZIPs without extracting archive paths."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import re
import sys
import zipfile
from datetime import datetime, timezone

MAX_ENTRIES = 20000
MAX_TOTAL_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_TEXT_FILE = 64 * 1024 * 1024
MAX_JSON_FILE = 8 * 1024 * 1024
MAX_JSON_CHARS = 24000
MAX_LOG_MATCHES_PER_FILE = 250

IMPORTANT = re.compile(
    r"error|fail|warn|fallback|denied|not supported|unsupported|"
    r"mali|kbase|csf|gralloc|swapchain|submit|mem_alloc|"
    r"vulkan|panvk|bc_|shader|timeout|device_lost",
    re.I,
)
TARGETED = re.compile(
    r"P0A-V19-FULLPLANE|cpu-linear-probe|mapper load|mapper.*failed|"
    r"HardwareBuffer|AHardwareBuffer|dma[_ -]?buf|vk_android_probe_linear_ahb|"
    r"vk_android_get_ahb_layout|ANativeWindow_(lock|unlockAndPost)|"
    r"vkCreateAndroidSurfaceKHR|vkCreateSwapchainKHR|vkAcquireNextImageKHR|"
    r"vkQueuePresentKHR|PHASE present|FPS_RESIZED",
    re.I,
)
TEXT_SUFFIXES = {".log", ".txt", ".out", ".err"}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_archive_path(raw: str, root: pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(raw)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Unsafe archive path: {raw}")
    resolved = (root / p).resolve()
    resolved.relative_to(root.resolve())
    if not resolved.is_file() or resolved.suffix.lower() != ".zip":
        raise ValueError(f"Not a ZIP file inside the repository: {raw}")
    return resolved


def inspect_one(path: pathlib.Path, report_path: pathlib.Path) -> None:
    lines: list[str] = []
    lines += [
        "PANPROBE / ANDROID DIAGNOSTIC ARCHIVE INSPECTION",
        f"Archive: {path.name}",
        f"Bytes: {path.stat().st_size}",
        f"SHA-256: {sha256(path)}",
        f"Inspected UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    with zipfile.ZipFile(path, "r") as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ENTRIES:
            raise ValueError(f"Archive has {len(infos)} files; limit is {MAX_ENTRIES}")
        total = sum(i.file_size for i in infos)
        if total > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError(f"Uncompressed size {total} exceeds 1 GiB safety limit")

        lines += [
            f"Files: {len(infos)}",
            f"Total uncompressed bytes: {total}",
            "",
            "=== FILE INVENTORY ===",
        ]
        for info in sorted(infos, key=lambda x: x.filename):
            # Do not extract entries; path traversal names remain inert.
            lines.append(f"{info.filename} ({info.file_size} bytes)")

        lines += ["", "=== JSON CONTENTS ==="]
        for info in sorted(infos, key=lambda x: x.filename):
            if pathlib.PurePosixPath(info.filename).suffix.lower() != ".json":
                continue
            lines.append(f"\n--- {info.filename} ---")
            if info.file_size > MAX_JSON_FILE:
                lines.append(f"[Skipped: JSON is larger than {MAX_JSON_FILE} bytes]")
                continue
            try:
                with zf.open(info, "r") as stream:
                    obj = json.load(io.TextIOWrapper(stream, encoding="utf-8", errors="replace"))
                rendered = json.dumps(obj, ensure_ascii=False, indent=2)
                lines.append(rendered[:MAX_JSON_CHARS])
                if len(rendered) > MAX_JSON_CHARS:
                    lines.append("[JSON output truncated]")
            except Exception as exc:
                lines.append(f"[JSON parse error: {exc}]")

        lines += ["", "=== IMPORTANT LOG LINES ==="]
        important_count = 0
        targeted_count = 0
        for info in sorted(infos, key=lambda x: x.filename):
            suffix = pathlib.PurePosixPath(info.filename).suffix.lower()
            if suffix not in TEXT_SUFFIXES:
                continue
            if info.file_size > MAX_TEXT_FILE:
                lines.append(f"\n--- {info.filename}: skipped ({info.file_size} bytes > scan limit) ---")
                continue
            matches: list[str] = []
            targeted: list[str] = []
            try:
                with zf.open(info, "r") as stream:
                    text_stream = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
                    for n, line in enumerate(text_stream, 1):
                        clipped = line.rstrip("\r\n")[:1200]
                        if IMPORTANT.search(clipped) and len(matches) < MAX_LOG_MATCHES_PER_FILE:
                            matches.append(f"{n}: {clipped}")
                        if TARGETED.search(clipped) and len(targeted) < MAX_LOG_MATCHES_PER_FILE:
                            targeted.append(f"{n}: {clipped}")
            except Exception as exc:
                matches.append(f"[read error: {exc}]")
            if matches:
                lines.append(f"\n--- {info.filename} ({len(matches)} emitted important lines) ---")
                lines.extend(matches)
                important_count += len(matches)
            if targeted:
                lines.append(f"\n--- TARGETED WSI / GRALLOC / AHB: {info.filename} ({len(targeted)} emitted lines) ---")
                lines.extend(targeted)
                targeted_count += len(targeted)

        lines += [
            "",
            f"Important log lines emitted: {important_count}",
            f"Targeted WSI / Gralloc / AHB lines emitted: {targeted_count}",
            "",
            "Notes:",
            "- This report is a text/log triage aid, not a Vulkan CTS certification.",
            "- No ZIP entries were extracted; unsafe archive paths were never written to disk.",
        ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT {report_path} ({report_path.stat().st_size} bytes)")
    print("\n".join(lines[-min(80, len(lines)):]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("archives", nargs="+")
    args = parser.parse_args()
    root = pathlib.Path.cwd().resolve()
    output_dir = pathlib.Path(args.output_dir)
    ok = True

    for index, raw in enumerate(args.archives, 1):
        try:
            archive = safe_archive_path(raw, root)
            stem = re.sub(r"[^A-Za-z0-9._-]+", "_", archive.stem)[:80] or f"archive-{index}"
            report = output_dir / f"{stem}-inspection.txt"
            inspect_one(archive, report)
        except Exception as exc:
            ok = False
            print(f"ERROR {raw}: {exc}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
