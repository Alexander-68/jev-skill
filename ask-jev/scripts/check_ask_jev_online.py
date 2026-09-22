"""Live check: sends one billable request using JEV_API_KEY; no retries."""

import json
from pathlib import Path
import subprocess
import sys


def main():
    skill = Path(__file__).resolve().parents[1]
    example = skill.joinpath("SKILL.md").read_text(encoding="utf-8")
    payload = example.split("<<'JEV_REQUEST'\n", 1)[1].split("\nJEV_REQUEST", 1)[0]
    run = subprocess.run(
        [sys.executable, str(skill / "scripts/ask_jev.py")],
        input=payload, text=True, capture_output=True,
    )
    print(run.stdout, end="")
    print(run.stderr, end="", file=sys.stderr)
    if run.returncode:
        raise SystemExit(run.returncode)
    answers = json.loads(run.stdout)["answers"]
    refund, route, urgency = (answers[name] for name in
                              ("refund_requested", "route", "urgency"))
    assert refund["type"] == "noul" and 0 <= refund["noul"] <= 1
    assert route["type"] == "choice" and route["choice"] in ("billing", "support")
    assert urgency["type"] == "score" and 0 <= urgency["score"] <= 2
    assert refund["noul"] > 0.5 and route["choice"] == "billing"
    print("Live example passed: all three answer types, ranges, and expected refund/billing results.")


if __name__ == "__main__":
    main()
