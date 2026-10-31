# 🐧 rxbootstrap

**The little engine that brings ReyaanshOS to life!**

Welcome to `rxbootstrap` — the tool used to build the root filesystem and bootable images for **ReyaanshOS-Reworked**.

It's Debian underneath, but with our own tweaks, configs, and a little bit of personality. This is where the magic (and occasional debugging) happens. 🚀

## 🖥️ Supported Architectures

- **ARM64** (`arm64`) — for ARM-powered devices.
- **AMD64** (`amd64`) — for regular PCs and laptops.

## 📦 Where Does the Rootfs Come From?

We don't build everything from scratch. The [rootfs_mirror](https://github.com/ReyaanshOS-Reworked/rootfs_mirror) repository hosts the base Debian root filesystems that `rxbootstrap` uses.

## ⚡ Getting Started

Grab the code:

```bash
git clone https://github.com/ReyaanshOS-Reworked/rxbootstrap.git
cd rxbootstrap
```

### Build for ARM64

```bash
python3 main.py --arch=arm64
```

### Build for AMD64

```bash
python3 main.py --arch=amd64
```

And that's it! Let the bootstrapper do its thing. ☕

## 🔐 Default Login

For builds using the default root password:

| Login | Value |
|---|---|
| Username | `root` |
| Password | `reyaansh` |

**Important:** Change the default password after your first boot. Don't leave the same password on an internet-connected machine!

## 🔗 Explore the Project

- 🏠 **GitHub Organization:** https://github.com/ReyaanshOS-Reworked
- 📦 **Rootfs Mirror:** https://github.com/ReyaanshOS-Reworked/rootfs_mirror
- 📖 **Documentation:** https://ReyaanshOS-Reworked.github.io

## 📜 License

Check out the `LICENSE` file for licensing details.

---

**Made with Linux, Python, and probably too much terminal time.**

*rxbootstrap — Building ReyaanshOS, one rootfs at a time.* 🐧
