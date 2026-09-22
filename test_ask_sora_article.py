"""Offline check: python3 test_ask_sora_article.py."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

import ask_sora_article


script = Path(__file__).resolve().with_name("ask_sora_article.py")
with tempfile.TemporaryDirectory() as folder:
    article = Path(folder) / "article.md"
    text = "# Synthetic article\n\nAn API shutdown is scheduled. 退款\n"
    article.write_text(text, encoding="utf-8")
    command = [sys.executable, str(script), str(article), "--dry-run"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["state"] == text
    assert sorted(q["type"] for q in payload["questions"].values()) == [
        "choice", "choice", "noul", "noul", "score",
    ]
    for status in (0, 1):
        stderr = StringIO()
        with patch.object(sys, "argv", [str(script), str(article)]), \
                patch("ask_sora_article.subprocess.run") as call, \
                patch("ask_sora_article.perf_counter", side_effect=[10.0, 10.125]), \
                redirect_stderr(stderr):
            call.return_value.returncode = status
            try:
                ask_sora_article.main()
            except SystemExit as error:
                assert error.code == status
            else:
                raise AssertionError("Expected helper exit status")
            call.assert_called_once()
        assert "125.0 ms" in stderr.getvalue()
    article.write_text("   ", encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and "Article must contain text" in result.stderr
    article.write_text("x" * 32_000, encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and "conservative Jev budget" in result.stderr

print("Offline article checks passed.")
