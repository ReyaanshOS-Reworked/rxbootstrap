import os
import sys
import tarfile
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime

ROOTFS_URLS = {
    "arm64": "https://github.com/ReyaanshOS-Reworked/rootfs_mirror/raw/refs/heads/main/base_rootfs/debian-arm64-rootfs.tar.xz",
    "amd64": "https://github.com/ReyaanshOS-Reworked/rootfs_mirror/raw/refs/heads/main/base_rootfs/debian-amd64-rootfs.tar.xz"
}

VERSION = "26.12"
ARCH = None

ROOT = Path(__file__).resolve().parent
TMP = ROOT / "tmp"
ROOTFS = TMP / "rootfs"
PATCHES = ROOT / "patches"
OUT = ROOT / "out"
DOWNLOAD = TMP / "rootfs.tar.xz"


def arg_reader(name):
    for arg in sys.argv:
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1].strip('"')
    return None


def progress(block_num, block_size, total_size):
    downloaded = block_num * block_size

    if total_size > 0:
        percent = min(downloaded * 100 / total_size, 100)
        bar_size = 35
        filled = int(bar_size * percent / 100)
        bar = "#" * filled + "-" * (bar_size - filled)

        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)

        print(
            f"\r[{bar}] {percent:5.1f}% "
            f"{downloaded_mb:.1f}/{total_mb:.1f} MB",
            end="",
            flush=True
        )


def download_rootfs():
    print("\n[1/4] Downloading Debian rootfs...")

    urllib.request.urlretrieve(
        ROOTFS_URLS[ARCH],
        DOWNLOAD,
        reporthook=progress
    )

    print("\nDownload complete!")


def extract_rootfs():
    print("\n[2/4] Extracting rootfs...")

    ROOTFS.mkdir(parents=True, exist_ok=True)

    with tarfile.open(DOWNLOAD, "r:xz") as archive:
        archive.extractall(
            path=ROOTFS,
            filter="fully_trusted"
        )

    print("Extraction complete!")


def apply_patches():
    print("\n[3/4] Applying patches...")

    if not PATCHES.exists():
        print("No patches directory found. Skipping.")
        return

    for source in PATCHES.rglob("*"):
        if source.is_dir():
            continue

        relative_path = source.relative_to(PATCHES)
        destination = ROOTFS / relative_path

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        print(f"Installed: {relative_path}")

    print("Patches applied!")


def repack_rootfs():
    print("\n[4/4] Repacking rootfs...")

    date = datetime.now().strftime("%Y%m%d")

    output_dir = OUT / ARCH
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / (
        f"reyaanshos-{VERSION}-{ARCH}-{date}.tar.xz"
    )

    with tarfile.open(output_file, "w:xz", preset=6) as archive:
        for item in ROOTFS.iterdir():
            archive.add(item, arcname=item.name)

    print(f"\nBuild complete!")
    print(f"Output: {output_file}")


def cleanup():
    print("\nCleaning temporary files...")

    if TMP.exists():
        shutil.rmtree(TMP)

    print("Cleanup complete!")


def main():
    global ARCH

    ARCH = arg_reader("--arch")

    if ARCH not in ROOTFS_URLS:
        print("Usage:")
        print("  python3 main.py --arch=arm64")
        print("  python3 main.py --arch=amd64")
        sys.exit(1)

    try:
        TMP.mkdir(parents=True, exist_ok=True)

        download_rootfs()
        extract_rootfs()
        apply_patches()
        repack_rootfs()

    except Exception as error:
        print(f"\nBuild failed: {error}")
        sys.exit(1)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
