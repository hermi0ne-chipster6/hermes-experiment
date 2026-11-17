"""Decode a retained desktop screenshot using the SDK's existing Pillow."""
import json
import sys

from PIL import Image


def inspect_image(path):
    with Image.open(path) as screenshot:
        assert screenshot.format in {"PNG", "JPEG"}, screenshot.format
        screenshot.verify()
    # verify() checks container integrity; load() also decodes the pixel data.
    with Image.open(path) as screenshot:
        screenshot.load()
        assert screenshot.width > 0 and screenshot.height > 0, screenshot.size
        return {"format": screenshot.format, "width": screenshot.width,
                "height": screenshot.height, "mode": screenshot.mode}


if __name__ == "__main__":
    print(json.dumps(inspect_image(sys.argv[1])))
