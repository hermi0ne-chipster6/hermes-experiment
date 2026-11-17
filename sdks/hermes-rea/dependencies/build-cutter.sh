#!/bin/bash
set -euo pipefail
cd "$CRAFT_PART_SRC"
image="$CRAFT_PART_SRC/Cutter-v2.5.0-Linux-Qt5-x86_64.AppImage"
test -f "$image"
printf '%s  %s\n' c796077954b419bd6ac36fafd0a0df36f21c8c90219dbfcfb486b34e0ad4bbc0 "$image" | sha256sum -c -
chmod +x "$image"
# Extract the official runtime once at build time; no FUSE or privileged mount.
"$image" --appimage-extract > "$CRAFT_PART_BUILD/cutter-extraction.log"
install -d "$CRAFT_PART_INSTALL/providers/cutter" "$CRAFT_PART_INSTALL/providers/bin"
cp -a squashfs-root/. "$CRAFT_PART_INSTALL/providers/cutter/"
chmod -R a+rX "$CRAFT_PART_INSTALL/providers/cutter"
test -x "$CRAFT_PART_INSTALL/providers/cutter/usr/bin/cutter"
test -r "$CRAFT_PART_INSTALL/providers/cutter/usr/lib/python3.11/site-packages/PySide2/QtCore.cpython-311-x86_64-linux-gnu.so"
ln -s ../../wrappers/cutter "$CRAFT_PART_INSTALL/providers/bin/cutter"
# Preserve every upstream bundled notice and library; do not prune the AppDir.
install -Dm644 "$CRAFT_PROJECT_DIR/assets/licenses/cutter/COPYING" \
    "$CRAFT_PART_INSTALL/providers/cutter/COPYING"
