"""Ask Jev five questions about article Markdown; --dry-run prints the request."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent / "ask-jev/scripts"))
from ask_jev import validate


QUESTIONS = {
    "api_shutdown": {
        "type": "noul",
        "instructions": "Does the article report a confirmed shutdown of the Sora API?",
        "criteria": {
            "true": "The article explicitly reports an announced or completed Sora API shutdown.",
            "false": "The article discusses speculation, a temporary outage, or does not confirm a shutdown.",
        },
    },
    "migration_guidance": {
        "type": "noul",
        "instructions": "Does the article provide actionable migration guidance for Sora API users?",
        "criteria": {
            "true": "It identifies a replacement service or concrete steps users can take to migrate.",
            "false": "It gives no concrete migration steps or replacement service; general advice is insufficient.",
        },
    },
    "shutdown_status": {
        "type": "choice",
        "instructions": "How does the article describe the Sora API shutdown status at publication?",
        "criteria": {
            "completed": "The API has already shut down.",
            "scheduled": "A shutdown is confirmed but still in the future.",
            "unconfirmed": "Shutdown is a rumor or possibility, not confirmed.",
            "unclear": "The text does not establish the status.",
        },
    },
    "primary_affected_group": {
        "type": "choice",
        "instructions": "Which group does the article primarily describe as directly affected by this change?",
        "criteria": {
            "api_users": "Developers or organizations integrating the Sora API.",
            "consumer_users": "People using a consumer Sora application or website.",
            "both": "API and consumer users are both central affected groups.",
            "unclear": "The article does not identify an affected user group.",
        },
    },
    "operational_impact": {
        "type": "score",
        "instructions": "Rate the operational impact on existing Sora API integrations supported by the article.",
        "criteria": [
            "No operational disruption is described.",
            "Minor adjustments are described while integrations remain functional.",
            "A future shutdown requires migration, but current integrations still work.",
            "Access has ended or is ending immediately, preventing continued operation without migration.",
            "The article explicitly reports widespread operational failures with substantial downstream consequences.",
        ],
    },
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path, help="UTF-8 article Markdown file")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON without calling Jev")
    args = parser.parse_args()
    try:
        article = args.article.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        parser.error(str(error))
    if not article.strip():
        parser.error("Article must contain text.")
    request = {"state": article, "questions": QUESTIONS}
    try:
        validate(request)
    except ValueError as error:
        parser.error(str(error))
    payload = json.dumps(request, ensure_ascii=False, indent=2)
    if args.dry_run:
        print(payload)
        return
    helper = Path(__file__).resolve().parent / "ask-jev/scripts/ask_jev.py"
    started = perf_counter()
    result = subprocess.run([sys.executable, str(helper)], input=payload, encoding="utf-8")
    elapsed_ms = (perf_counter() - started) * 1000
    print(f"Jev call: {elapsed_ms:.1f} ms (includes helper startup)", file=sys.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
