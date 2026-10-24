# ask-jev skill

The main purpose of this repository is the [ask-jev skill](ask-jev/SKILL.md),
located in the [`ask-jev/`](ask-jev/) subfolder. The Sora article and accompanying
script demonstrate how to use this skill to turn article text into structured
Jev decisions.

## Demonstration: Sora article → Jev decisions

`article.md` contains the user-supplied article as plain Markdown. Its claims
are input for analysis, not independently verified facts.

Requires Python 3 and an OpenRouter key in `JEV_API_KEY`. In your own Bash terminal:

```bash
read -rsp "OpenRouter API key: " JEV_API_KEY; echo
export JEV_API_KEY
python3 ask_sora_article.py article.md --dry-run  # Validate and preview; no API call
python3 ask_sora_article.py article.md            # One billable call; JSON output
```

The script asks two `noul` questions (confirmed shutdown, migration guidance),
two `choice` questions (shutdown status, affected group), and one `score` question
(operational impact, 0–4). Edit `QUESTIONS` in `ask_sora_article.py` to change the
rubrics. Noul values are yes-probabilities; scores may be fractional. The custom
impact rubric runs from no described disruption to widespread consequential failures.

Calls use `typesafe/jev-1.14` through the bundled helper, with a 60-second
timeout and no retries. Article text and questions go to OpenRouter and TypeSafe.
Jev's [documented context limit](https://openrouter.ai/~typesafe/jev-latest) is
32,000 tokens (checked September 22, 2026). Both preview and live calls enforce
a conservative 32,000-byte ASCII-JSON budget across the text and all questions,
with no output token reserve. This is not exact token counting;
oversized input is rejected without truncation or a network call.

## Demonstration: persons and cats in images

`ask_images.py` sends every `.png`, `.jpg`, `.jpeg`, or `.webp` in a folder
(webp is converted to png) to Jev with four questions: how many persons and
how many cats (`none`, `1`, `2`, `3`, `more_than_3`), and one `box` for all
persons and one for all cats. It writes `<name>.jev.png` with red person and
blue cat boxes (skipped when the count is `none`) and prints the answers.

```bash
python3 ask_images.py . --dry-run  # Preview requests; no API call
python3 ask_images.py .            # One billable call per image
```

Requires Pillow. Image input is documented for TypeSafe's API but not for
OpenRouter's Decisions API, so OpenRouter may reject these requests.

Offline checks:

```bash
python3 test_ask_images.py
python3 test_ask_sora_article.py
python3 ask-jev/scripts/test_ask_jev.py
```
