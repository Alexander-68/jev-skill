---
name: ask-jev
description: Ask Jev through OpenRouter for structured decisions (choices, yes/no, scores, image bounding boxes) from text or image context. Use when the user says ask-jev or asks to consult Jev.
---

# Ask Jev

Translate the user's request into typed questions, call Jev, and report its answers.
Requires Python 3 and an OpenRouter key in `JEV_API_KEY`, inherited by the agent's
process. Never put the key in a file, command argument, chat message, or output.

## Missing API key

If the helper reports that `JEV_API_KEY` is missing, pause the API call and ask
the user to enter their OpenRouter key privately in their own Bash terminal:

```bash
read -rsp "OpenRouter API key: " JEV_API_KEY; echo
export JEV_API_KEY
```

Explain that they run these commands unchanged, paste the actual key when the
prompt appears, and press Enter; input is invisible. They must then launch the
agent from that same terminal and repeat their `ask-jev` request. Exporting in
another terminal cannot update an already-running agent's environment.
Do not run this interactive prompt in an agent tool terminal or ask the user
to send the key through chat. Check availability without printing its value.

## Form the request

Use the user's supplied context as `state` (text, object, or array). Include
relevant conversation context only when the request refers to it; omit secrets
and unrelated material. The context will be sent to OpenRouter and TypeSafe.

Create a `questions` object keyed by short, stable IDs. Each question has
`type`, `instructions`, and `criteria`:

- `choice`: criteria is an object mapping each allowed answer to its description.
  Preserve the user's choices. For independent multi-label decisions, use one
  `noul` question per label instead of forcing a single choice.
- `noul`: a yes/no judgment; criteria has string keys `true` and `false`, each
  describing when that answer applies.
- `score`: criteria is an array of descriptions ordered from lowest to highest.
  Jev scores are fractional, zero-based level indices. Preserve the user's level
  order and labels. For a 1–5 scale, supply five descriptions and report raw score
  plus the explicitly labeled conversion `raw + 1`. Never silently change scales.
- `box`: locates something in an image; has only `type` and `instructions`
  (no `criteria`). The answer has `box` with `top`, `bottom`, `left`, `right`
  as 0–1 fractions of image height/width from the top-left, plus `confidence`
  (may be `null`). A box is returned even if the object is absent, so pair it
  with a `choice` or `noul` presence question.

### Images

Make `state` an array and put each image in it as an `image_url` part holding a
base64 data URL, text before images:
`{"state": ["Door camera frame:", {"type": "image_url", "image_url": {"url":
"data:image/jpeg;base64,..."}}], "questions": {...}}`. The Decisions API takes
only `data:image/png` or `data:image/jpeg` URLs, not HTTP(S) links; convert
others (for example webp) first. Images must be 256–1,568 pixels per side,
78,400–2,458,624 pixels in total, and at most 16 MiB decoded; Jev rejects rather
than resizes. No extra headers are needed. `box` questions need an image in `state`.
Images go to OpenRouter and TypeSafe.

Use one question per judgment and batch questions sharing the same context into
one request. Write concrete, neutral criteria without inventing facts. If the
user gives a clear judgment but no rubric, create a compact rubric and disclose
it with the result. If missing choices or criteria materially change what is
being asked, clarify before calling. Jev cannot generate prose explanations,
code, or arbitrary open-ended answers; turn a question into a defined decision
only when that preserves its intent. Do not use Jev for arithmetic or counting.

### Context budget

Jev Latest currently has a [32,000-token context window](https://openrouter.ai/~typesafe/jev-latest)
(verified September 22, 2026). Budget the state, question IDs, instructions, and
all criteria together. Image parts are not counted by the guard.
The helper enforces a conservative 32,000-byte limit on ASCII-serialized request
JSON before opening a connection. This is not an exact token count and may reject
text that would fit; escaped Unicode also counts toward the budget. No output
token reserve is deducted from this input budget. Recheck the documented limit when the
latest alias changes; do not raise this guard based on a characters-per-token guess.

If the guard rejects a request, shorten context only while preserving evidence
needed for the judgment, or split independent questions into smaller batches
with the needed context in each. Never silently truncate, drop criteria, split
a judgment that requires the whole document, or combine chunk probabilities
as though Jev evaluated the full text. If lossless reduction is not possible,
ask the user to narrow the task. Do not automatically retry rejected requests.

## Call

Run the bundled helper by its absolute path, resolved relative to this SKILL.md.
Feed JSON through stdin using a quoted heredoc (choose a delimiter absent from
the input). JSON-escape user text; never interpolate it as shell code.

```bash
python3 /absolute/path/to/ask-jev/scripts/ask_jev.py <<'JEV_REQUEST'
{
  "state": "A customer was charged twice and requests a refund.",
  "questions": {
    "refund_requested": {
      "type": "noul",
      "instructions": "Does the customer request a refund?",
      "criteria": {"true": "Requests money back.", "false": "Does not request money back."}
    },
    "route": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {"billing": "Charges or refunds.", "support": "Product usage help."}
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this case?",
      "criteria": ["Routine inquiry.", "Financial issue needing prompt attention.", "Ongoing critical loss."]
    }
  }
}
JEV_REQUEST
```

The helper pins the model to `typesafe/jev-1.14` (Jev 1.14.0) and sends one authenticated
POST to `https://openrouter.ai/api/alpha/decisions`. This is the Decisions API,
not chat completions; do not send `messages` or `response_format`. It has a
60-second timeout and no automatic retries. On failure, report it; never
substitute a different model or fabricate a result. After a timeout, explain
that the request may have been processed before offering another call.

## Present

Attribute answers to Jev and match IDs back to the user's questions. Show the
selected choice, yes-probability (`noul`), or fractional score with its scale.
Include returned probabilities and confidence when useful, keeping those fields
distinct; confidence is not necessarily the winning option's probability.
Do not turn a probability into a categorical verdict without an explicit
threshold. Preserve uncertainty and report missing answers as an error.
Mention any inferred rubric or score conversion. Never attribute your own
explanation to Jev: it returns decisions, not reasoning. These results do not
authorize executing a recommended action. Include returned model and cost when
available, especially if the user asks. Supply raw JSON when requested.

## References and check

- [Model alias](https://openrouter.ai/~typesafe/jev-latest)
- [Decisions request and response schema](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request)
- [Jev capabilities](https://docs.typesafe.ai/concepts/system-one)
- [Images and box questions](https://docs.typesafe.ai/api)

Run the offline check: `python3 scripts/test_ask_jev.py` from this skill folder.
Run the live check: `python3 scripts/check_ask_jev_online.py` from this skill
folder. It tests the example above with one billable request using `JEV_API_KEY`,
prints the response, and checks all three answer types and expected decisions.
