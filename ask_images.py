"""Ask Jev to count and box persons and cats in every image in a folder.

Writes <name>.jev.png with drawn boxes and prints the answers as JSON.
--dry-run prints each request (image data elided) without calling Jev.
"""

import argparse
import base64
import io
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent / "ask-jev/scripts"))
from ask_jev import ask, validate


EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
COUNTS = {
    "none": "Visible {0}: zero.",
    "1": "Visible {0}: exactly one.",
    "2": "Visible {0}: exactly two.",
    "3": "Visible {0}: exactly three.",
    "more_than_3": "Visible {0}: more than three.",
}
TARGETS = {"person": ("persons", "red"), "cat": ("cats", "blue")}
QUESTIONS = {}
for target, (plural, _) in TARGETS.items():
    QUESTIONS[target + "_count"] = {
        "type": "choice",
        "instructions": f"How many {plural} are visible in the image? Count partly visible ones too.",
        "criteria": {k: v.format(plural) for k, v in COUNTS.items()},
    }
    QUESTIONS[target + "_box"] = {
        "type": "box",
        "instructions": f"Locate the smallest box enclosing all {plural} in the image.",
    }


def request_for(image):
    # ponytail: Jev takes png/jpg only, so anything else (webp) is re-encoded as png.
    if image.suffix.lower() in (".png", ".jpg", ".jpeg"):
        data, fmt = image.read_bytes(), image.suffix.lower().lstrip(".")
    else:
        buffer = io.BytesIO()
        Image.open(image).save(buffer, "PNG")
        data, fmt = buffer.getvalue(), "png"
    return {
        "state": "photo",
        "questions": QUESTIONS,
        "assets": {"photo": {"type": "image", "format": fmt,
                             "data_base64": base64.b64encode(data).decode("ascii")}},
    }


def draw(image, answers, output):
    picture = Image.open(image).convert("RGB")
    width, height = picture.size
    pen = ImageDraw.Draw(picture)
    for target, (_, color) in TARGETS.items():
        count = answers[target + "_count"]["choice"]
        if count == "none":
            continue  # a box for something absent is meaningless
        box = answers[target + "_box"]["box"]
        xy = (box["left"] * width, box["top"] * height, box["right"] * width, box["bottom"] * height)
        pen.rectangle(xy, outline=color, width=max(2, width // 200))
        pen.text((xy[0] + 4, xy[1] + 4), f"{target}: {count}", fill=color,
                 font_size=max(12, height // 30))
    picture.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--dry-run", action="store_true", help="Print requests without calling Jev")
    args = parser.parse_args()
    images = sorted(p for p in args.folder.iterdir()
                    if p.suffix.lower() in EXTENSIONS and not p.name.endswith(".jev.png"))
    if not images:
        parser.error(f"No images in {args.folder}.")
    results = {}
    for image in images:
        request = request_for(image)
        validate(request)
        if args.dry_run:
            request["assets"]["photo"]["data_base64"] = "<elided>"
            results[image.name] = request
            continue
        answers = ask(request)["answers"]
        output = image.with_name(image.stem + ".jev.png")
        draw(image, answers, output)
        results[image.name] = {"answers": answers, "visualization": output.name}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("ask_images: " + str(error), file=sys.stderr)
        sys.exit(1)
