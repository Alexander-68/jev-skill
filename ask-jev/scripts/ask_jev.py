#!/usr/bin/env python3
"""Send a typed Jev decision request from stdin; print the JSON response."""

import http.client
import json
import os
import sys


# ponytail: conservative byte budget for the 32,000-token context; use the
# provider's tokenizer if exact packing is needed.
MAX_REQUEST_BYTES = 32_000


def validate(payload):
    if not isinstance(payload, dict) or set(payload) != {"state", "questions"}:
        raise ValueError("Input must contain exactly state and questions.")
    if not isinstance(payload["state"], (str, dict, list)) or not payload["state"]:
        raise ValueError("state must be nonempty text, an object, or an array.")
    questions = payload["questions"]
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty object.")
    for name, question in questions.items():
        if not name or not isinstance(question, dict):
            raise ValueError("Each question needs an ID and an object.")
        if set(question) != {"type", "instructions", "criteria"}:
            raise ValueError("Each question needs type, instructions, and criteria.")
        if not isinstance(question["instructions"], str) or not question["instructions"].strip():
            raise ValueError("Question instructions must be nonempty text.")
        kind, criteria = question["type"], question["criteria"]
        if kind == "score":
            valid = isinstance(criteria, list) and len(criteria) >= 1
            descriptions = criteria if valid else []
        elif kind in ("choice", "noul"):
            valid = isinstance(criteria, dict) and bool(criteria) and all(criteria)
            if kind == "noul":
                valid = valid and set(criteria) == {"true", "false"}
            descriptions = criteria.values() if valid else []
        else:
            raise ValueError("Question type must be choice, noul, or score.")
        if not valid or not all(isinstance(x, str) and x.strip() for x in descriptions):
            raise ValueError("Invalid criteria; provide nonempty text descriptions.")
    # ASCII JSON also budgets escaped Unicode, nested state, IDs, and all rubrics.
    size = len(json.dumps(payload, ensure_ascii=True, allow_nan=False).encode("ascii"))
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
    body = json.dumps({**payload, "model": "~typesafe/jev-latest"}, allow_nan=False)
    connection = http.client.HTTPSConnection("openrouter.ai", timeout=60)
    try:
        connection.request("POST", "/api/alpha/decisions", body.encode("utf-8"), {
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        })
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
    try:
        print(json.dumps(ask(json.load(sys.stdin)), ensure_ascii=False, indent=2))
    except (ValueError, OSError, http.client.HTTPException) as error:
        # Do not print request data, headers, or raw provider error bodies.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        key = os.environ.get("JEV_API_KEY", "").strip()
        print("ask-jev: " + (message.replace(key, "[redacted]") if key else message), file=sys.stderr)
        sys.exit(1)
