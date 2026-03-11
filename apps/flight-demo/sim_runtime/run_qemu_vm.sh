#!/usr/bin/env bash
set -euo pipefail

VM_ROOT="${ARRAKIS_QEMU_VM_DIR:-$HOME/Developer/arrakis-vm}"
DISK_IMAGE="$VM_ROOT/arrakis-vm.qcow2"
SEED_IMAGE="$VM_ROOT/seed.dmg"
QEMU_EFI_CODE="${ARRAKIS_QEMU_EFI_CODE:-/opt/homebrew/share/qemu/edk2-aarch64-code.fd}"
QEMU_EFI_VARS="$VM_ROOT/edk2-aarch64-vars.fd"

if [[ ! -f "$DISK_IMAGE" || ! -f "$SEED_IMAGE" ]]; then
  echo "[sim-runtime] VM disk/seed missing. Run ./bootstrap_qemu_vm.sh first." >&2
  exit 1
fi

if [[ ! -f "$QEMU_EFI_CODE" ]]; then
  echo "[sim-runtime] missing QEMU EFI code at $QEMU_EFI_CODE" >&2
  exit 1
fi

if [[ ! -f "$QEMU_EFI_VARS" ]]; then
  cp /opt/homebrew/share/qemu/edk2-arm-vars.fd "$QEMU_EFI_VARS"
fi

exec qemu-system-aarch64 \
  -machine virt,highmem=on,accel=hvf \
  -cpu host \
  -smp 6 \
  -m 8192 \
  -device virtio-gpu-pci \
  -device qemu-xhci \
  -device usb-kbd \
  -device usb-tablet \
  -drive if=pflash,format=raw,readonly=on,file="$QEMU_EFI_CODE" \
  -drive if=pflash,format=raw,file="$QEMU_EFI_VARS" \
  -drive if=virtio,file="$DISK_IMAGE",format=qcow2 \
  -drive if=virtio,file="$SEED_IMAGE",format=raw \
  -nic user,model=virtio-net-pci,hostfwd=tcp::2222-:22,hostfwd=udp::14550-:14550,hostfwd=udp::5600-:5600 \
  -display default,show-cursor=on
