#!/usr/bin/env python3
"""Append authenticated Switchbrew homebrew components to an Atmosphere ZIP.

The published asset hashes are pinned to the 2025-11-15 official releases.
Do not replace these values without verifying the official upstream assets.
"""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

HBL_VERSION = "v2.4.5"
HBMENU_VERSION = "v3.6.1"
HBL_ASSET_SHA256 = "853df8526557b82c6b2018a8a102d22e8306687415e49653530dfd9a1d603b32"
HBMENU_ZIP_SHA256 = "4790c58fdd75c4bcc644fa8135fa11c380cb3ebaf685e400e336031972410ee7"
CORE_ENTRIES = (
    "atmosphere/package3",
    "atmosphere/reboot_payload.bin",
    "switch/daybreak.nro",
    "switch/haze.nro",
    "switch/reboot_to_payload.nro",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_asset(path: Path, sha256: str) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"Missing official release asset: {path}")
    data = path.read_bytes()
    actual = digest(data)
    if actual != sha256:
        raise RuntimeError(
            f"Official asset SHA256 mismatch for {path}: {actual} != {sha256}"
        )
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--hbl", type=Path, required=True)
    parser.add_argument("--hbmenu-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    hbl = verify_asset(args.hbl, HBL_ASSET_SHA256)
    hbmenu_zip = verify_asset(args.hbmenu_zip, HBMENU_ZIP_SHA256)

    with ZipFile(args.hbmenu_zip, "r") as source:
        matching = [
            name for name in source.namelist()
            if not name.endswith("/") and PurePosixPath(name).name == "hbmenu.nro"
        ]
        if len(matching) != 1:
            raise RuntimeError(
                f"Expected exactly one hbmenu.nro in the official ZIP; found {matching}"
            )
        hbmenu = source.read(matching[0])
    if len(hbmenu) < 4096:
        raise RuntimeError("Official hbmenu.nro is unexpectedly small")

    additions = {
        "atmosphere/hbl.nsp": hbl,
        "hbmenu.nro": hbmenu,
    }

    with ZipFile(args.archive, "r") as existing:
        names = existing.namelist()
        for entry in CORE_ENTRIES:
            if names.count(entry) != 1 or not existing.getinfo(entry).file_size:
                raise RuntimeError(f"Invalid or missing core Atmosphere entry: {entry}")
        for entry, contents in additions.items():
            if names.count(entry) > 1:
                raise RuntimeError(f"Duplicate homebrew entry: {entry}")
            if entry in names and digest(existing.read(entry)) != digest(contents):
                raise RuntimeError(
                    f"Existing {entry} conflicts with the pinned Switchbrew release"
                )

    with ZipFile(args.archive, "a", compression=ZIP_DEFLATED, compresslevel=9) as target:
        for path, contents in additions.items():
            if path not in target.namelist():
                target.writestr(path, contents, compress_type=ZIP_DEFLATED)

    with ZipFile(args.archive, "r") as verify:
        for path, contents in additions.items():
            if verify.namelist().count(path) != 1:
                raise RuntimeError(f"Missing or duplicate archive entry: {path}")
            if digest(verify.read(path)) != digest(contents):
                raise RuntimeError(f"Archive data corrupted after merging: {path}")
        bad_entry = verify.testzip()
        if bad_entry is not None:
            raise RuntimeError(f"ZIP CRC verification failed: {bad_entry}")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        "Sources for added Homebrew components (not built from Atmosphere source)\n"
        f"nx-hbloader {HBL_VERSION}\n"
        "https://github.com/switchbrew/nx-hbloader/releases/tag/v2.4.5\n"
        f"hbl.nsp SHA256: {HBL_ASSET_SHA256}\n"
        f"Installed as: atmosphere/hbl.nsp\n\n"
        f"nx-hbmenu {HBMENU_VERSION}\n"
        "https://github.com/switchbrew/nx-hbmenu/releases/tag/v3.6.1\n"
        f"nx-hbmenu_v3.6.1.zip SHA256: {HBMENU_ZIP_SHA256}\n"
        f"hbmenu.nro SHA256: {digest(hbmenu)}\n"
        "Installed as: hbmenu.nro\n",
        encoding="utf-8",
    )
    print("Switchbrew assets verified and integrated in:", args.archive)


if __name__ == "__main__":
    main()
