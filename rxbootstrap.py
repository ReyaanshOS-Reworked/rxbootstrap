#!/usr/bin/env python3
"""
rxbootstrap - ReyaanshOS Rootfs & Bootable Image Builder
"""

import os
import sys
import tarfile
import shutil
import urllib.request
import subprocess
import tempfile
import argparse
import time
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
VERSION = "1.2.1"
TOOL_NAME = "rxbootstrap"

ROOTFS_URLS = {
    "arm64": "https://github.com/ReyaanshOS-Reworked/rootfs_mirror/raw/refs/heads/main/base_rootfs/debian-arm64-rootfs.tar.xz",
    "amd64": "https://github.com/ReyaanshOS-Reworked/rootfs_mirror/raw/refs/heads/main/base_rootfs/debian-amd64-rootfs.tar.xz",
}

ROOT = Path(__file__).resolve().parent
TMP = ROOT / "tmp"
ROOTFS = TMP / "rootfs"
PATCHES = ROOT / "patches"
OUT = ROOT / "out"
DOWNLOAD = TMP / "rootfs.tar.xz"

DEFAULT_IMG_SIZE = "4G"
DEFAULT_HOSTNAME = "reyaanshos"
DEFAULT_ROOT_PASSWORD = "reyaansh"

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def log(msg: str):
    print(f"[{TOOL_NAME}] {msg}")

def run(cmd, check=True, capture=False, env=None, cwd=None, quiet=False):
    if isinstance(cmd, (list, tuple)):
        printable = " ".join(str(c) for c in cmd)
        if not quiet:
            print(f"  $ {printable}")
        result = subprocess.run(
            list(cmd), check=check, capture_output=capture,
            text=True, env=env, cwd=cwd
        )
    else:
        if not quiet:
            print(f"  $ {cmd}")
        result = subprocess.run(
            cmd, shell=True, check=check,
            capture_output=capture, text=True, env=env, cwd=cwd
        )
    return result

def progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(downloaded * 100 / total_size, 100)
        bar_size = 35
        filled = int(bar_size * percent / 100)
        bar = "█" * filled + "░" * (bar_size - filled)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)
        print(
            f"\r  [{bar}] {percent:5.1f}%  {downloaded_mb:.1f}/{total_mb:.1f} MB",
            end="", flush=True,
        )

def require_root():
    if os.geteuid() != 0:
        log("Error: this operation requires root privileges.")
        log(f"Please re-run with: sudo python3 {Path(__file__).name} ...")
        sys.exit(1)

def check_host_tools(needed: list[str]):
    missing = [t for t in needed if shutil.which(t) is None]
    if missing:
        log(f"Missing required host tools: {', '.join(missing)}")
        sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Core steps
# ─────────────────────────────────────────────────────────────
def download_rootfs(arch: str, force: bool = False):
    log("[1/7] Downloading Debian rootfs...")
    if DOWNLOAD.exists() and not force:
        log(f"  Using cached download: {DOWNLOAD}")
        return
    DOWNLOAD.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(ROOTFS_URLS[arch], DOWNLOAD, reporthook=progress)
    print()
    log("Download complete.")

def extract_rootfs(force: bool = False):
    log("[2/7] Extracting rootfs...")
    if ROOTFS.exists() and any(ROOTFS.iterdir()) and not force:
        log("  Rootfs already extracted. Skipping (use --force to re-extract).")
        return
    if ROOTFS.exists():
        shutil.rmtree(ROOTFS)
    ROOTFS.mkdir(parents=True, exist_ok=True)
    with tarfile.open(DOWNLOAD, "r:xz") as archive:
        archive.extractall(path=ROOTFS, filter="fully_trusted")
    log("Extraction complete.")

def apply_patches():
    log("[3/7] Applying patches...")
    if not PATCHES.exists():
        log("  No patches/ directory found. Skipping.")
        return
    count = 0
    for source in PATCHES.rglob("*"):
        if source.is_dir():
            continue
        relative = source.relative_to(PATCHES)
        dest = ROOTFS / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        print(f"  → {relative}")
        count += 1
    log(f"Applied {count} patch file(s).")

def setup_chroot():
    resolv = ROOTFS / "etc" / "resolv.conf"
    if not resolv.exists() and not resolv.is_symlink():
        shutil.copy2("/etc/resolv.conf", resolv)

    for fs in ["proc", "sys", "dev", "dev/pts"]:
        target = ROOTFS / fs
        target.mkdir(parents=True, exist_ok=True)
        run(["mount", "--bind", f"/{fs}", str(target)], check=False, quiet=True)

def teardown_chroot():
    for fs in ["dev/pts", "dev", "sys", "proc"]:
        target = ROOTFS / fs
        run(["umount", "-l", str(target)], check=False, quiet=True)

def chroot_run(cmd: str, check=True, env=None):
    full_env = os.environ.copy()
    full_env["DEBIAN_FRONTEND"] = "noninteractive"
    full_env["LC_ALL"] = "C"
    if env:
        full_env.update(env)
    return run(
        ["chroot", str(ROOTFS), "/bin/bash", "-c", cmd],
        check=check,
        env=full_env,
    )

def install_packages(extra_packages: list[str], arch: str, create_image: bool,
                     hostname: str, root_password: str):
    log("[4/7] Installing packages into rootfs...")
    if not extra_packages and not create_image:
        log("  No packages requested and not creating image. Skipping.")
        return

    setup_chroot()
    try:
        essential = [
            "passwd", "systemd", "systemd-sysv", "dbus", "sudo",
            "locales", "ca-certificates", "net-tools", "iproute2",
            "openssh-server", "apt-utils", "e2fsprogs",
        ]
        if create_image:
            if arch == "amd64":
                boot_packages = ["linux-image-amd64", "initramfs-tools",
                                 "grub-efi-amd64", "grub-common", "efibootmgr"]
            else:
                boot_packages = ["linux-image-arm64", "initramfs-tools",
                                 "grub-efi-arm64", "grub-common", "efibootmgr"]
        else:
            boot_packages = []

        all_pkgs = list(dict.fromkeys(essential + boot_packages + extra_packages))
        log(f"  Packages: {', '.join(all_pkgs)}")
        chroot_run("apt-get update -qq")
        chroot_run("apt-get install -y --no-install-recommends " + " ".join(all_pkgs))
        chroot_run("apt-get clean")
        chroot_run("rm -rf /var/lib/apt/lists/*")
        # Keep root-password setup; all other OS configuration comes from patches/.
        chroot_run("printf '%s\\n' " + repr("root:" + root_password) + " | /usr/sbin/chpasswd")
        log("Packages installed.")
    finally:
        teardown_chroot()

def create_bootable_image(arch: str, img_size: str, hostname: str) -> Path:
    log("[5/7] Creating bootable disk image...")
    check_host_tools(["parted", "mkfs.vfat", "mkfs.ext4", "rsync", "losetup"])

    date = datetime.now().strftime("%Y%m%d")
    output_dir = OUT / arch
    output_dir.mkdir(parents=True, exist_ok=True)
    img_path = output_dir / f"reyaanshos-{VERSION}-{arch}-{date}.img"

    log(f"  Creating sparse image ({img_size}): {img_path.name}")
    run(["truncate", "-s", img_size, str(img_path)])

    # GPT layout: EFI (512 MiB) + root
    run(["parted", "-s", str(img_path), "mklabel", "gpt"])
    run(["parted", "-s", str(img_path), "mkpart", "ESP", "fat32", "1MiB", "513MiB"])
    run(["parted", "-s", str(img_path), "set", "1", "esp", "on"])
    run(["parted", "-s", str(img_path), "mkpart", "primary", "ext4", "513MiB", "100%"])

    loop = run(["losetup", "-f", "--show", "-P", str(img_path)], capture=True).stdout.strip()
    log(f"  Loop device: {loop}")

    efi_part = f"{loop}p1"
    root_part = f"{loop}p2"
    mnt = None

    try:
        run(["mkfs.vfat", "-F32", "-n", "EFI", efi_part])
        run(["mkfs.ext4", "-L", "rootfs", "-F", root_part])

        mnt = Path(tempfile.mkdtemp(prefix="rxbootstrap-mnt-"))
        efi_mnt = mnt / "boot" / "efi"

        run(["mount", root_part, str(mnt)])
        efi_mnt.mkdir(parents=True, exist_ok=True)
        run(["mount", efi_part, str(efi_mnt)])

        log("  Copying rootfs into image...")
        run([
            "rsync", "-aHAX", "--info=progress2",
            "--exclude=/tmp/*", "--exclude=/proc/*",
            "--exclude=/sys/*", "--exclude=/dev/*",
            f"{ROOTFS}/", f"{mnt}/"
        ])

        # Preserve /etc/fstab supplied through patches/. Generate only a fallback.
        fstab_path = mnt / "etc" / "fstab"
        if not fstab_path.exists():
            fstab_path.parent.mkdir(parents=True, exist_ok=True)
            fstab = (f"# /etc/fstab generated by {TOOL_NAME}\n"
                     "LABEL=rootfs  /          ext4  defaults,noatime  0 1\n"
                     "LABEL=EFI     /boot/efi  vfat  umask=0077        0 1\n")
            fstab_path.write_text(fstab)

        # Temporary mounts for grub-install
        for fs in ["proc", "sys", "dev", "dev/pts"]:
            target = mnt / fs
            target.mkdir(parents=True, exist_ok=True)
            run(["mount", "--bind", f"/{fs}", str(target)], check=False, quiet=True)

        log("  Installing GRUB (UEFI)...")
        if arch == "amd64":
            run([
                "chroot", str(mnt), "/usr/sbin/grub-install",
                "--target=x86_64-efi",
                "--efi-directory=/boot/efi",
                "--bootloader-id=ReyaanshOS",
                "--recheck", "--no-nvram"
            ])
            # Also install the removable fallback path (very useful for QEMU/USB)
            run([
                "chroot", str(mnt), "/usr/sbin/grub-install",
                "--target=x86_64-efi",
                "--efi-directory=/boot/efi",
                "--bootloader-id=BOOT",
                "--removable", "--recheck", "--no-nvram"
            ], check=False)
        else:
            run([
                "chroot", str(mnt), "/usr/sbin/grub-install",
                "--target=arm64-efi",
                "--efi-directory=/boot/efi",
                "--bootloader-id=ReyaanshOS",
                "--recheck", "--no-nvram"
            ])
            run([
                "chroot", str(mnt), "/usr/sbin/grub-install",
                "--target=arm64-efi",
                "--efi-directory=/boot/efi",
                "--bootloader-id=BOOT",
                "--removable", "--recheck", "--no-nvram"
            ], check=False)

        # Use GRUB settings copied from patches/; do not rewrite them here.
        run([
            "chroot", str(mnt), "/bin/bash", "-c",
            "export PATH=/usr/sbin:/usr/bin:/sbin:/bin; update-grub"
        ])
        run([
            "chroot", str(mnt), "/bin/bash", "-c",
            "export PATH=/usr/sbin:/usr/bin:/sbin:/bin; update-initramfs -u -k all"
        ], check=False)

        log("  GRUB installation finished.")
    finally:
        if mnt and mnt.exists():
            for fs in ["dev/pts", "dev", "sys", "proc"]:
                run(["umount", "-l", str(mnt / fs)], check=False, quiet=True)
            run(["umount", "-l", str(mnt / "boot" / "efi")], check=False, quiet=True)
            run(["umount", "-l", str(mnt)], check=False, quiet=True)
            shutil.rmtree(mnt, ignore_errors=True)
        run(["losetup", "-d", loop], check=False, quiet=True)

    log(f"Bootable image ready → {img_path}")
    return img_path

def repack_rootfs(arch: str) -> Path:
    log("[5/7] Repacking rootfs tarball...")
    date = datetime.now().strftime("%Y%m%d")
    output_dir = OUT / arch
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"reyaanshos-{VERSION}-{arch}-{date}.tar.xz"

    with tarfile.open(output_file, "w:xz", preset=6) as archive:
        for item in ROOTFS.iterdir():
            archive.add(item, arcname=item.name)

    log(f"Rootfs tarball ready → {output_file}")
    return output_file


def find_newest_image(arch: str) -> Path:
    """Return the most recently modified .img in out/<arch>/."""
    img_dir = OUT / arch
    if not img_dir.exists():
        log(f"No output directory: {img_dir}")
        sys.exit(1)
    images = sorted(img_dir.glob("*.img"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not images:
        log(f"No .img files found in {img_dir}")
        log("Build one first with: --create-image or --qemu")
        sys.exit(1)
    newest = images[0]
    log(f"Using existing image: {newest}")
    return newest

def launch_qemu(img_path: Path, arch: str, memory: str = "2048", smp: str = "2",
                  graphic: bool = False, orientation: str = "horizontal"):
    log("[6/7] Launching QEMU...")
    log(f"  Requested guest orientation: {orientation}")
    log("  QEMU cannot force guest rotation; set it in the guest display configuration.")
    if arch == "amd64":
        qemu_bin = "qemu-system-x86_64"
        extra = []
        if Path("/dev/kvm").exists():
            extra += ["-enable-kvm", "-cpu", "host"]
        else:
            extra += ["-cpu", "qemu64"]
    else:
        qemu_bin = "qemu-system-aarch64"
        extra = ["-cpu", "cortex-a72", "-machine", "virt,gic-version=3"]

    check_host_tools([qemu_bin])

    # Arch + Debian OVMF locations
    ovmf_code_candidates = [
        "/usr/share/edk2/x64/OVMF_CODE.4m.fd",
        "/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd",
        "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd",
        "/usr/share/edk2/x64/OVMF_CODE.fd",
        "/usr/share/OVMF/OVMF_CODE.fd",
        "/usr/share/edk2/ovmf/OVMF_CODE.fd",
        "/usr/share/qemu/OVMF.fd",
        "/usr/share/AAVMF/AAVMF_CODE.fd",
    ]
    ovmf_vars_candidates = [
        "/usr/share/edk2/x64/OVMF_VARS.4m.fd",
        "/usr/share/edk2-ovmf/x64/OVMF_VARS.fd",
        "/usr/share/edk2/x64/OVMF_VARS.fd",
        "/usr/share/OVMF/OVMF_VARS.fd",
        "/usr/share/edk2/ovmf/OVMF_VARS.fd",
    ]

    ovmf_code = next((c for c in ovmf_code_candidates if Path(c).exists()), None)
    ovmf_vars = next((c for c in ovmf_vars_candidates if Path(c).exists()), None)

    cmd = [
        qemu_bin,
        "-m", memory,
        "-smp", smp,
        "-drive", f"file={img_path},format=raw,if=virtio",
        "-nic", "user,model=virtio-net-pci,hostfwd=tcp::2222-:22",
    ]

    if not graphic:
        cmd += ["-nographic"]
    else:
        cmd += ["-vga", "std", "-display", "vnc=:0"]

    if ovmf_code:
        # Proper pflash UEFI (required for reliable EFI boot)
        cmd += [
            "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        ]
        if ovmf_vars:
            # Writable copy of VARS so EFI can store boot entries
            vars_copy = Path(tempfile.gettempdir()) / "rxbootstrap-OVMF_VARS.fd"
            shutil.copy2(ovmf_vars, vars_copy)
            cmd += [
                "-drive", f"if=pflash,format=raw,file={vars_copy}",
            ]
        log(f"  Using UEFI firmware: {ovmf_code}")
    else:
        log("  ERROR: No OVMF firmware found. Install it:")
        log("    Arch:    sudo pacman -S edk2-ovmf")
        log("    Debian:  sudo apt install ovmf")
        log("  Without UEFI the image will hang at 'Booting from Hard Disk...'")
        sys.exit(1)

    cmd += extra

    log(f"Command: {' '.join(cmd)}")
    log("Tips:")
    log("  • Exit QEMU          → Ctrl+C")
    log("  • SSH into the guest → ssh -p 2222 root@localhost")
    log(f"  • Root password     → {DEFAULT_ROOT_PASSWORD}")
    print()

    if graphic:
        log("Starting QEMU + VNC viewer...")
        qemu_proc = subprocess.Popen(cmd)
        import time
        time.sleep(1.5)

        viewer = None
        for candidate in ["vncviewer", "vinagre", "remote-viewer", "gvncviewer"]:
            if shutil.which(candidate):
                viewer = candidate
                break

        if viewer:
            log(f"Opening {viewer} → localhost:5900")
            try:
                if viewer == "remote-viewer":
                    subprocess.Popen([viewer, "vnc://127.0.0.1:5900"])
                else:
                    subprocess.Popen([viewer, "localhost:5900"])
            except Exception as e:
                log(f"Could not launch viewer: {e}")
                log("Connect manually: vncviewer localhost:5900")
        else:
            log("No VNC viewer found. Install one:")
            log("  sudo pacman -S tigervnc")
            log("Then connect to: localhost:5900")

        try:
            qemu_proc.wait()
        except KeyboardInterrupt:
            qemu_proc.terminate()
            qemu_proc.wait()
    else:
        os.execvp(qemu_bin, cmd)

def cleanup(keep: bool = False):
    if keep:
        log("Keeping temporary files (--keep-tmp).")
        return
    log("Cleaning temporary files...")
    teardown_chroot()
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    log("Cleanup done.")

# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def desktop_environment_packages(de: str) -> list[str]:
    packages = {
        "none": [],
        "plasma-mobile": ["plasma-mobile", "sddm"],
        "plasma-desktop": ["task-kde-desktop", "sddm"],
    }
    return packages[de]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="ReyaanshOS rootfs builder + bootable image creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  sudo {TOOL_NAME} --arch=amd64
  sudo {TOOL_NAME} --arch=amd64 --add=vim,htop,curl
  sudo {TOOL_NAME} --arch=amd64 --create-image
  sudo {TOOL_NAME} --arch=amd64 --qemu --add=neofetch
  sudo {TOOL_NAME} --arch=amd64 --qemu --img-size=8G --hostname=mybox --root-password='s3cret'
""",
    )

    p.add_argument("--arch", required=True, choices=["amd64", "arm64"])
    p.add_argument("--add", default="", help="Comma-separated extra packages")
    p.add_argument("--create-image", action="store_true",
                   help="Produce a bootable .img (UEFI + systemd)")
    p.add_argument("--qemu", action="store_true",
                   help="Create image and launch QEMU")
    p.add_argument("--img-size", default=DEFAULT_IMG_SIZE)
    p.add_argument("--hostname", default=DEFAULT_HOSTNAME)
    p.add_argument("--root-password", default=DEFAULT_ROOT_PASSWORD)
    p.add_argument("--force", action="store_true",
                   help="Force re-download and re-extract")
    p.add_argument("--keep-tmp", action="store_true")
    p.add_argument("--memory", default="2048",
                   help="QEMU memory in MB (default: 2048)")
    p.add_argument("--smp", default="2",
                   help="QEMU CPU count (default: 2)")
    p.add_argument("--graphic", action="store_true",
                   help="Use graphical display instead of -nographic")
    p.add_argument("--DE", choices=["none", "plasma-mobile", "plasma-desktop"],
                   default="none", help="Desktop environment packages to install")
    p.add_argument("--oriantation", "--orientation", dest="orientation",
                   choices=["vertical", "horizontal"], default="horizontal",
                   help="Requested guest orientation; configure rotation inside the guest")
    p.add_argument("--qemu-without-build", action="store_true",
                   help="Skip build and launch QEMU with the newest image in out/<arch>/")
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {VERSION}")

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Quick path: just boot an existing image
    if args.qemu_without_build:
        img = find_newest_image(args.arch)
        launch_qemu(img, args.arch,
                    memory=args.memory, smp=args.smp,
                    graphic=args.graphic, orientation=args.orientation)
        return

    create_image = args.create_image or args.qemu
    packages = [p.strip() for p in args.add.split(",") if p.strip()]
    packages = list(dict.fromkeys(packages + desktop_environment_packages(args.DE)))

    if packages or create_image:
        require_root()

    start = time.time()
    log(f"Starting {TOOL_NAME} v{VERSION} (arch={args.arch})")

    try:
        TMP.mkdir(parents=True, exist_ok=True)

        download_rootfs(args.arch, force=args.force)
        extract_rootfs(force=args.force)
        install_packages(
            packages, args.arch, create_image,
            args.hostname, args.root_password
        )
        apply_patches()

        if create_image:
            img_path = create_bootable_image(
                args.arch, args.img_size, args.hostname
            )
            if args.qemu:
                cleanup(keep=args.keep_tmp)
                launch_qemu(img_path, args.arch,
                            memory=args.memory, smp=args.smp,
                            graphic=args.graphic, orientation=args.orientation)
            else:
                log(f"Build finished in {time.time()-start:.1f}s")
                log(f"Image: {img_path}")
        else:
            tar_path = repack_rootfs(args.arch)
            log(f"Build finished in {time.time()-start:.1f}s")
            log(f"Tarball: {tar_path}")

    except KeyboardInterrupt:
        print()
        log("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        log(f"Build failed: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if not args.qemu:
            cleanup(keep=args.keep_tmp)

if __name__ == "__main__":
    main()
