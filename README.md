# rxbootstrap

**The official bootstrap tool for ReyaanshOS-Reworked.**

`rxbootstrap` is a project dedicated to building and preparing root filesystems for ReyaanshOS-Reworked, a Debian-based operating system project.

## Supported Architectures

- **ARM64** (`arm64`)
- **AMD64** (`amd64`)

## Base Root Filesystems

The [rootfs_mirror](https://github.com/ReyaanshOS-Reworked/rootfs_mirror) repository contains the base Debian root filesystems used by `rxbootstrap` for each supported architecture.

## Usage

Clone the repository:

```bash
git clone https://github.com/ReyaanshOS-Reworked/rxbootstrap.git
cd rxbootstrap
```

Run the bootstrapper:

```bash
python3 main.py --arch=arm64
```

For AMD64:

```bash
python3 main.py --arch=amd64
```

## Related Links

- **GitHub Organization:** https://github.com/ReyaanshOS-Reworked
- **Rootfs Mirror:** https://github.com/ReyaanshOS-Reworked/rootfs_mirror
- **Documentation:** https://ReyaanshOS-Reworked.github.io

## License

See the `LICENSE` file in this repository.

---

*rxbootstrap — Part of ReyaanshOS-Reworked.*
