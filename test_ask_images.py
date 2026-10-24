"""Offline check: python3 test_ask_images.py."""

import base64
import io
import json
from pathlib import Path
import sys
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch

from PIL import Image

import ask_images


answers = {
    "person_count": {"type": "choice", "choice": "none"},
    "person_box": {"type": "box", "box": {"top": 0, "bottom": 1, "left": 0, "right": 1}},
    "cat_count": {"type": "choice", "choice": "2"},
    "cat_box": {"type": "box", "box": {"top": 0.25, "bottom": 0.75, "left": 0.5, "right": 1.0}},
}
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    Image.new("RGB", (200, 100), "white").save(folder / "a.webp")
    Image.new("RGB", (200, 100), "white").save(folder / "b.jpg")
    Image.new("RGB", (3000, 1500), "white").save(folder / "big.jpg")
    Image.new("RGB", (400, 300), "white").save(folder / "ok.jpg")
    (folder / "notes.txt").write_text("not an image")

    def sent(name):
        url = ask_images.request_for(folder / name)["state"][1]["image_url"]["url"]
        head, data = url.split(",")
        return head, Image.open(io.BytesIO(base64.b64decode(data)))

    request = ask_images.request_for(folder / "a.webp")
    assert sent("a.webp")[0] == "data:image/png;base64" and sent("a.webp")[1].format == "PNG"
    assert sent("ok.jpg")[0] == "data:image/jpeg;base64"  # in range: sent as is
    head, big = sent("big.jpg")
    assert head == "data:image/png;base64" and big.size == (1568, 784)
    head, small = sent("b.jpg")
    assert head == "data:image/png;base64" and small.size == (560, 280)
    assert set(request["questions"]["cat_count"]["criteria"]) == {
        "none", "1", "2", "3", "more_than_3"}

    out = io.StringIO()
    with patch.object(sys, "argv", ["ask_images.py", str(folder)]), \
            patch("ask_images.ask", return_value={"answers": answers}) as call, \
            redirect_stdout(out):
        ask_images.main()
    assert call.call_count == 4
    assert json.loads(out.getvalue())["a.webp"]["visualization"] == "a.jev.png"
    drawn = Image.open(folder / "a.jev.png")
    assert drawn.getpixel((0, 50)) == (255, 255, 255)  # no person box when count is none
    assert drawn.getpixel((150, 25)) == (0, 0, 255)  # cat box edge

    with patch.object(sys, "argv", ["ask_images.py", str(folder)]), \
            patch("ask_images.ask", return_value={"answers": answers}) as call, \
            redirect_stdout(io.StringIO()):
        ask_images.main()  # earlier .jev.png outputs are not re-sent
    assert call.call_count == 4

print("Offline image checks passed.")
