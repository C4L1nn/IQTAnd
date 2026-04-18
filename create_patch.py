#!/usr/bin/env python3
"""
iqtMusic patch builder.

Builds a patch zip from ``dist/iqtMusic``.
The patch contains:
  - new and modified files
  - a small manifest that lists deleted files

That lets the updater keep installed copies in sync instead of leaving
renamed or removed files behind forever.
"""

import hashlib
import json
import os
import sys
import time
import zipfile

DIST_DIR = os.path.join("dist", "iqtMusic")
OUTPUT = "iqtMusic_patch.zip"
MANIFEST = "dist_manifest.json"
PATCH_MANIFEST_NAME = "__iqtm_patch_manifest__.json"

# Bu dosyalar GERÇEKTEN DEĞİŞMEDİKÇE patch'e eklenmez.
# (iqtMusic.exe APP_VERSION içerdiğinden her versiyon değişikliğinde dahil edilmelidir)
SKIP_IF_UNCHANGED: set = set()


def _md5(path: str) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _scan_dist() -> dict[str, str]:
    result: dict[str, str] = {}
    for root, _, files in os.walk(DIST_DIR):
        for name in files:
            abs_path = os.path.join(root, name)
            arc_name = os.path.relpath(abs_path, DIST_DIR).replace("\\", "/")
            result[arc_name] = _md5(abs_path)
    return result


def _load_previous_manifest() -> dict[str, str]:
    if not os.path.exists(MANIFEST):
        return {}
    with open(MANIFEST, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict) and isinstance(raw.get("files"), dict):
        raw = raw["files"]
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _save_manifest(current: dict[str, str]):
    payload = {
        "version": 2,
        "hash_algorithm": "md5",
        "generated_at": int(time.time()),
        "files": current,
    }
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _add_file(zf: zipfile.ZipFile, arc_name: str):
    abs_path = os.path.join(DIST_DIR, arc_name.replace("/", os.sep))
    size_mb = os.path.getsize(abs_path) / 1_048_576
    zf.write(abs_path, arc_name)
    print(f"  + {arc_name:<55}  {size_mb:>6.1f} MB")


def main():
    full = "--all" in sys.argv
    reset = "--reset" in sys.argv

    if not os.path.isdir(DIST_DIR):
        print(f"\nERROR: '{DIST_DIR}' not found.")
        print("Run: pyinstaller iqtMusic.spec")
        sys.exit(1)

    if reset and os.path.exists(MANIFEST):
        os.remove(MANIFEST)
        print(f"  Manifest reset: {MANIFEST}\n")

    print(f"\n{'-' * 65}")
    print(f"  iqtMusic Patch Builder -> {OUTPUT}")
    print(f"{'-' * 65}")

    current = _scan_dist()
    previous = _load_previous_manifest()

    changed_files: list[str] = []
    new_files: list[str] = []
    modified_files: list[str] = []
    deleted_files = sorted(set(previous) - set(current))

    if full:
        changed_files = sorted(current)
        print(f"  Mode: full dist snapshot ({len(changed_files)} files)\n")
    elif not previous:
        changed_files = sorted(current)
        print(
            "  Mode: first build - no manifest, packaging whole dist "
            f"({len(changed_files)} files)\n"
        )
    else:
        for arc_name, md5 in sorted(current.items()):
            if arc_name not in previous:
                new_files.append(arc_name)
                changed_files.append(arc_name)
            elif previous[arc_name] != md5:
                # Değişmemiş sayılan dosyaları atla
                if arc_name in SKIP_IF_UNCHANGED:
                    continue
                modified_files.append(arc_name)
                changed_files.append(arc_name)

        print("  Mode: incremental diff\n")
        if modified_files:
            print(f"  Modified ({len(modified_files)} files):")
            for item in modified_files:
                print(f"    ~ {item}")
            print()
        if new_files:
            print(f"  New      ({len(new_files)} files):")
            for item in new_files:
                print(f"    + {item}")
            print()
        if deleted_files:
            print(f"  Deleted  ({len(deleted_files)} files):")
            for item in deleted_files:
                print(f"    - {item}")
            print()
        if not changed_files and not deleted_files:
            print("  No file changes detected - patch is not needed.")
            print(f"{'-' * 65}\n")
            return

    patch_manifest = {
        "format": 1,
        "generated_at": int(time.time()),
        "full_build": bool(full or not previous),
        "changed_files": changed_files,
        "deleted_files": deleted_files,
    }

    print(
        "  Writing patch:"
        f" {len(changed_files)} changed/new file(s),"
        f" {len(deleted_files)} deleted file(s)\n"
    )
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(
            PATCH_MANIFEST_NAME,
            json.dumps(patch_manifest, indent=2, ensure_ascii=False),
        )
        print(f"  + {PATCH_MANIFEST_NAME:<55}  manifest")
        for arc_name in changed_files:
            _add_file(zf, arc_name)

    _save_manifest(current)

    patch_size = os.path.getsize(OUTPUT) / 1_048_576
    patch_sha256 = _sha256(OUTPUT)
    full_size = sum(
        os.path.getsize(os.path.join(root, name))
        for root, _, files in os.walk(DIST_DIR)
        for name in files
    ) / 1_048_576

    print(f"\n{'-' * 65}")
    print(f"  Patch size : {patch_size:>7.1f} MB  (full dist: {full_size:.0f} MB)")
    if full_size > 0:
        saved = full_size - patch_size
        percent = (1 - patch_size / full_size) * 100
        print(f"  Saved      : {saved:>7.1f} MB  (%{percent:.0f} smaller)")
    print(f"  SHA-256    : {patch_sha256}")
    print(f"{'-' * 65}")
    print(f"\n  Ready      : {OUTPUT}")
    print(f"  Manifest   : {MANIFEST}")
    print()
    print("  Release steps:")
    print("  1. Build: pyinstaller iqtMusic.spec")
    print("  2. Run : python create_patch.py")
    print(f"  3. Upload {OUTPUT} to the matching GitHub release tag")
    print("  4. GitHub will expose the asset SHA-256 digest automatically")
    print()


if __name__ == "__main__":
    main()
