"""Offline contract check: python3 scripts/test_ask_jev.py."""

import copy
import json
from unittest.mock import patch

from ask_jev import MAX_REQUEST_BYTES, ask, validate


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
    assert json.loads(body) == {**payload, "model": "~typesafe/jev-latest"}
    assert headers["Authorization"] == "Bearer test-key"
    connection.close.assert_called_once()

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
    assert connection.request.call_count == 1

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
