"""Offline contract check: python3 scripts/test_ask_jev.py."""

import copy
import json
from unittest.mock import patch

from ask_jev import MAX_REQUEST_BYTES, MODEL, ask, validate


payload = {
    "state": "Customer says: \"退款\"\nCosts $5; `do not execute`.",
    "questions": {
        "refund": {"type": "noul", "instructions": "Refund requested?",
                   "criteria": {"true": "Money back requested", "false": "No request"}},
        "team": {"type": "choice", "instructions": "Who handles it?",
                 "criteria": {"billing": "Money issues", "support": "Usage help"}},
        "urgency": {"type": "score", "instructions": "How urgent?",
                    "criteria": ["Routine", "Urgent"]},
    },
}
result = {"answers": {"refund": {"type": "noul", "noul": 0.95},
                      "team": {"type": "choice", "choice": "billing"},
                      "urgency": {"type": "score", "score": 0.8}}}

with patch.dict("os.environ", {"JEV_API_KEY": "test-key"}), \
        patch("ask_jev.http.client.HTTPSConnection") as transport:
    connection = transport.return_value
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = json.dumps(result).encode()
    assert ask(payload) == result
    transport.assert_called_once_with("openrouter.ai", timeout=60)
    method, path, body, headers = connection.request.call_args.args
    assert (method, path) == ("POST", "/api/alpha/decisions")
    assert json.loads(body) == {**payload, "model": MODEL}
    assert headers["Authorization"] == "Bearer test-key"
    assert "TypeSafe-Danger-Zone-Images" not in headers
    connection.close.assert_called_once()

    image = {"state": "photo", "assets": {"photo": {
        "type": "image", "format": "png", "data_base64": "x" * MAX_REQUEST_BYTES}},
        "questions": {"cat": {"type": "box", "instructions": "Locate the cat."}}}
    boxed = {"answers": {"cat": {"type": "box", "confidence": None, "box": {
        "top": 0.1, "bottom": 0.9, "left": 0.2, "right": 0.8}}}}
    response.read.return_value = json.dumps(boxed).encode()
    assert ask(image) == boxed  # image bytes do not count toward the text budget
    method, path, body, headers = connection.request.call_args.args
    assert json.loads(body)["assets"] == image["assets"]
    assert headers["TypeSafe-Danger-Zone-Images"] == "true"
    response.read.return_value = json.dumps(result).encode()
    calls = connection.request.call_count
    bad_images = [{**image, "assets": {}}, {**image, "assets": {"photo": {
        **image["assets"]["photo"], "format": "webp"}}},
        {**image, "questions": {"cat": {**image["questions"]["cat"], "criteria": {}}}},
        {k: v for k, v in image.items() if k != "assets"}]
    for bad in bad_images:
        try:
            ask(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid image request accepted")
    assert connection.request.call_count == calls

    for bad in ({}, {**payload, "questions": []}):
        try:
            ask(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid input accepted")
    bad = copy.deepcopy(payload)
    bad["questions"]["urgency"]["criteria"] = {"low": "Routine"}
    try:
        ask(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid score criteria accepted")
    assert connection.request.call_count == 2

    for status, data in [(401, {}), (429, {}), (200, {"error": {}}),
                         (200, {"answers": {}}), (200, [])]:
        response.status = status
        response.read.return_value = json.dumps(data).encode()
        before = connection.request.call_count
        try:
            ask(payload)
        except ValueError:
            pass
        else:
            raise AssertionError("Failed response accepted")
        assert connection.request.call_count == before + 1

with patch.dict("os.environ", {"JEV_API_KEY": ""}), \
        patch("ask_jev.http.client.HTTPSConnection") as transport:
    try:
        ask(payload)
    except ValueError as error:
        assert "JEV_API_KEY" in str(error)
    else:
        raise AssertionError("Missing key accepted")
    transport.assert_not_called()

with patch("ask_jev.http.client.HTTPSConnection") as transport:
    boundary = copy.deepcopy(payload)
    boundary["state"] = ""
    overhead = len(json.dumps(boundary).encode("ascii"))
    boundary["state"] = "x" * (MAX_REQUEST_BYTES - overhead)
    validate(boundary)
    boundary["state"] += "x"
    oversized = [boundary, {**payload, "state": {"text": ["退款" * 3000]}}]
    large_rubric = copy.deepcopy(payload)
    large_rubric["questions"]["refund"]["criteria"]["true"] = "x" * MAX_REQUEST_BYTES
    oversized.append(large_rubric)
    for bad in oversized:
        try:
            ask(bad)
        except ValueError as error:
            assert "conservative Jev budget" in str(error)
        else:
            raise AssertionError("Oversized input accepted")
    transport.assert_not_called()

print("Offline checks passed.")
