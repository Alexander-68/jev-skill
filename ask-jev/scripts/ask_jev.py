#!/usr/bin/env python3
"""Send a typed Jev decision request from stdin; print the JSON response."""

import http.client
import json
import os
import sys


# ponytail: conservative byte budget for the 32,000-token context; use the
# provider's tokenizer if exact packing is needed.
MAX_REQUEST_BYTES = 32_000
MODEL = "typesafe/jev-1.14"
IMAGE_FORMATS = {"png", "jpg", "jpeg"}


def validate(payload):
    if not isinstance(payload, dict) or not {"state", "questions"} <= set(payload)             or not set(payload) <= {"state", "questions", "assets"}:
        raise ValueError("Input must contain state and questions, plus optional assets.")
    assets = payload.get("assets", {})
    if not isinstance(assets, dict) or ("assets" in payload and not assets):
        raise ValueError("assets must be a nonempty object.")
    for name, asset in assets.items():
        if not name or not isinstance(asset, dict) or asset.get("type") != "image"                 or asset.get("format") not in IMAGE_FORMATS                 or not isinstance(asset.get("data_base64"), str) or not asset["data_base64"]:
            raise ValueError("Each asset needs type image, format png/jpg/jpeg, and data_base64.")
    if not isinstance(payload["state"], (str, dict, list)) or not payload["state"]:
        raise ValueError("state must be nonempty text, an object, or an array.")
    questions = payload["questions"]
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty object.")
    for name, question in questions.items():
        if not name or not isinstance(question, dict):
            raise ValueError("Each question needs an ID and an object.")
        kind = question.get("type")
        fields = {"type", "instructions"} if kind == "box" else {"type", "instructions", "criteria"}
        if set(question) != fields:
            raise ValueError("Each question needs type, instructions, and criteria (box: no criteria).")
        if not isinstance(question["instructions"], str) or not question["instructions"].strip():
            raise ValueError("Question instructions must be nonempty text.")
        if kind == "box":
            if not assets:
                raise ValueError("box questions need an image in assets.")
            continue
        criteria = question["criteria"]
        if kind == "score":
            valid = isinstance(criteria, list) and len(criteria) >= 1
            descriptions = criteria if valid else []
        elif kind in ("choice", "noul"):
            valid = isinstance(criteria, dict) and bool(criteria) and all(criteria)
            if kind == "noul":
                valid = valid and set(criteria) == {"true", "false"}
            descriptions = criteria.values() if valid else []
        else:
            raise ValueError("Question type must be choice, noul, score, or box.")
        if not valid or not all(isinstance(x, str) and x.strip() for x in descriptions):
            raise ValueError("Invalid criteria; provide nonempty text descriptions.")
    # ASCII JSON also budgets escaped Unicode, nested state, IDs, and all rubrics.
    # ponytail: image bytes are excluded; their token cost is undocumented.
    text = {k: v for k, v in payload.items() if k != "assets"}
    size = len(json.dumps(text, ensure_ascii=True, allow_nan=False).encode("ascii"))
    if size > MAX_REQUEST_BYTES:
        raise ValueError(
            f"Request is {size} serialized bytes; conservative Jev budget is "
            f"{MAX_REQUEST_BYTES} bytes for its 32,000-token context. "
            "Shorten state or split independent questions; nothing was sent or truncated."
        )


def ask(payload):
    validate(payload)
    key = os.environ.get("JEV_API_KEY", "").strip()
    if not key:
        raise ValueError("Set JEV_API_KEY to your OpenRouter API key.")
    body = json.dumps({**payload, "model": MODEL}, allow_nan=False)
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if "assets" in payload:
        # ponytail: TypeSafe's image opt-in; OpenRouter does not document assets.
        headers["TypeSafe-Danger-Zone-Images"] = "true"
    connection = http.client.HTTPSConnection("openrouter.ai", timeout=60)
    try:
        connection.request("POST", "/api/alpha/decisions", body.encode("utf-8"), headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"OpenRouter HTTP {response.status}; no retry was made.")
        result = json.loads(response.read())
    finally:
        connection.close()
    if not isinstance(result, dict) or "error" in result:
        raise ValueError("OpenRouter returned an error or invalid response.")
    answers = result.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(payload["questions"]):
        raise ValueError("OpenRouter returned missing or unexpected answers.")
    return result


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        print(json.dumps(ask(json.load(sys.stdin)), ensure_ascii=False, indent=2))
    except (ValueError, OSError, http.client.HTTPException) as error:
        # Do not print request data, headers, or raw provider error bodies.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        key = os.environ.get("JEV_API_KEY", "").strip()
        print("ask-jev: " + (message.replace(key, "[redacted]") if key else message), file=sys.stderr)
        sys.exit(1)
