#!/usr/bin/env bash
set -euo pipefail

VM_ROOT="${ARRAKIS_QEMU_VM_DIR:-$HOME/Developer/arrakis-vm}"
IMAGE_URL="${ARRAKIS_QEMU_IMAGE_URL:-https://cloud-images.ubuntu.com/minimal/releases/noble/release/ubuntu-24.04-minimal-cloudimg-arm64.img}"
BASE_IMAGE="$VM_ROOT/ubuntu-24.04-minimal-cloudimg-arm64.img"
DISK_IMAGE="$VM_ROOT/arrakis-vm.qcow2"
SEED_IMAGE="$VM_ROOT/seed.dmg"
SEED_DIR="$VM_ROOT/cloud-init"
SSH_PUBKEY="${ARRAKIS_QEMU_SSH_PUBKEY:-$HOME/.ssh/id_ed25519.pub}"

mkdir -p "$VM_ROOT" "$SEED_DIR"

if [[ ! -f "$BASE_IMAGE" ]]; then
  echo "[sim-runtime] downloading Ubuntu cloud image"
  curl -L -o "$BASE_IMAGE" "$IMAGE_URL"
fi

if [[ ! -f "$DISK_IMAGE" ]]; then
  qemu-img create -f qcow2 -b "$BASE_IMAGE" -F qcow2 "$DISK_IMAGE" 40G
fi

if [[ -f "$SSH_PUBKEY" ]]; then
  SSH_KEY_CONTENT="$(cat "$SSH_PUBKEY")"
else
  echo "[sim-runtime] warning: no SSH pubkey found at $SSH_PUBKEY; VM will rely on password login" >&2
  SSH_KEY_CONTENT=""
fi

cat >"$SEED_DIR/user-data" <<EOF
#cloud-config
hostname: arrakis-vm
manage_etc_hosts: true
users:
  - default
  - name: arrakis
    gecos: Arrakis VM User
    groups: [sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
$( [[ -n "$SSH_KEY_CONTENT" ]] && printf "    ssh_authorized_keys:\n      - %s\n" "$SSH_KEY_CONTENT" )
ssh_pwauth: true
chpasswd:
  list: |
    arrakis:arrakis
  expire: false
package_update: false
EOF

cat >"$SEED_DIR/meta-data" <<'EOF'
instance-id: arrakis-vm
local-hostname: arrakis-vm
EOF

rm -f "$SEED_IMAGE"
hdiutil create -size 8m -layout NONE -fs MS-DOS -volname cidata "$SEED_IMAGE" >/dev/null
hdiutil attach -mountpoint /tmp/arrakis-cidata "$SEED_IMAGE" >/dev/null
cp "$SEED_DIR/user-data" /tmp/arrakis-cidata/user-data
cp "$SEED_DIR/meta-data" /tmp/arrakis-cidata/meta-data
sync
hdiutil detach /tmp/arrakis-cidata >/dev/null

echo "[sim-runtime] qemu VM assets prepared"
echo "[sim-runtime] base image: $BASE_IMAGE"
echo "[sim-runtime] disk image: $DISK_IMAGE"
echo "[sim-runtime] seed image: $SEED_IMAGE"
