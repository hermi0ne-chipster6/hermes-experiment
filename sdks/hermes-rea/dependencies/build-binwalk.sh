#!/bin/bash
# Source and Cargo.lock are supplied by the checksum-pinned SDKcraft part.
set -euo pipefail
cd "$CRAFT_PART_SRC"
# Limit build concurrency for small development/build machines.
cargo build --release --locked --jobs "${CARGO_BUILD_JOBS:-2}"
install -Dm755 target/release/binwalk "$CRAFT_PART_INSTALL/providers/bin/binwalk"
install -Dm644 LICENSE "$CRAFT_PART_INSTALL/providers/licenses/binwalk/LICENSE"
cargo metadata --locked --format-version 1 > "$CRAFT_PART_INSTALL/providers/licenses/binwalk/cargo-metadata.json"
# Preserve bundled Rust crates' license/notice files alongside the executable.
/usr/bin/python3 - "$CRAFT_PART_INSTALL/providers/licenses/binwalk" <<'PY'
import json
from pathlib import Path
import shutil
import sys

destination = Path(sys.argv[1])
metadata = json.loads((destination / "cargo-metadata.json").read_text())
for package in metadata["packages"]:
    source = Path(package["manifest_path"]).parent
    for item in source.iterdir():
        if item.is_file() and item.name.lower().startswith(("license", "copying", "notice")):
            target = destination / (package["name"] + "-" + package["version"]) / item.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
PY
"$CRAFT_PART_INSTALL/providers/bin/binwalk" --version | grep -Fx 'binwalk 3.1.0'
