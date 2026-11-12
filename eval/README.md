# Evaluation set

`cases.jsonl` holds 52 labeled AI system descriptions. `run_eval.py` sends them to a running
screener and scores the answers.

## The set

| Expected class | Cases | What they cover |
| --- | --- | --- |
| `prohibited` | 9 | Every point of Article 5(1): (a) to (h) and point (ba) added by Regulation (EU) 2026/1744 |
| `high` | 16 | All eight Annex III areas; two Annex I Section A products (medical device, in vitro diagnostic); two Annex I Section B products (machine learning safety component under the Machinery Regulation, pedestrian emergency braking in cars), where Article 2(2) limits the provisions that apply; the Article 6(3) profiling rule; an Article 5(1)(f) safety exception; a high-risk system with Article 50 duties |
| `limited` | 9 | Article 50(1), 50(2) and 50(4); two general-purpose AI model providers |
| `minimal` | 9 | Spam filter, fraud detection (Annex III 5(b) carve-out), biometric verification, two Article 6(3) exemptions, Article 6(1a) and 6(1c), plain business uses |
| `not_covered` | 3 | AI-related descriptions the Act does not apply to: military use (Article 2(3)), research only (Article 2(6)), rule-based software that is not an AI system (Article 3(1)) |
| `unclear` | 4 | Descriptions that lack the one fact the class depends on |
| `out_of_scope` | 2 | An off-topic request and a prompt injection: the expected result has `in_scope: false` |

- 44 cases in English, 2 each in Dutch, French, German and Turkish.
- `difficulty`: 16 easy, 18 medium, 18 hard.
- 2 cases expect `gpai: true` (`gpai-open-weights-llm`, `gpai-frontier-chat`); a downstream
  provider that only calls another company's model (`lim-restaurant-voicebot`) expects `false`.
- 1 case accepts more than one class: `min-teacher-feedback-polish` (`minimal` or `limited`).
- The Article 5(1)(bb) point (child sexual abuse material) has no case on purpose: the provision
  is in the corpus, and such a description does not belong in a public test file.

Fields of a case:

| Field | Meaning |
| --- | --- |
| `id` | stable id, prefix by area (`pr-`, `hr-`, `edu-`, `fin-`, `infra-`, `bio-`, `le-`, `mig-`, `just-`, `prod-`, `lim-`, `gpai-`, `min-`, `nc-`, `unc-`, `oos-`) |
| `description` | what a founder or developer would type: two to five sentences, no legal terms that give the answer away |
| `role` | `provider`, `deployer` or `unknown`, sent to the API as is |
| `expected_class` | the label |
| `acceptable_classes` | classes also counted as correct; more than one only where the Act leaves room, and the `rationale` says why |
| `expected_refs` | corpus ids (`art-5-1`, `annex-III-4`, `art-6-1a`) a correct answer should cite |
| `gpai` | whether the general-purpose AI model step should say yes |
| `rationale` | the provision that decides the label, quoted or pointed to |

## How the labels were made

- Each description was written for one provision, then labeled against the text in `data/corpus.json`:
  the EUR-Lex consolidated version of Regulation (EU) 2024/1689 of 27 July 2026, which includes
  Regulation (EU) 2026/1744. Recitals come from the 2024 Official Journal text.
- The rationale quotes the deciding words of the article or annex point; recitals are used only
  where they give the Act's own example (recital 12 on rule-based software, 18 on emotions, 29 on
  significant harm, 50 on Annex I products, 53 on Article 6(3), 54 on biometric verification, 58 on
  fraud detection, 103 on monetised open-source components).
- The machinery case also rests on Regulation (EU) 2023/1230, Annex I Part A point 5 and Article
  25(2); the general-purpose AI case on the Commission guidelines C(2025) 7719 for the monetisation
  point (which does not change its class).
- Every case was re-read against the consolidated text, and again in a second, independent check
  against the text; refs, rationales and descriptions that gave the answer away were fixed. No
  lawyer has reviewed the labels.
- Classes:
  - `minimal` means the Act applies and none of Articles 5, 6 and 50 does. Systems the Act does not
    apply to are `not_covered`, and `minimal` is not accepted for them.
  - A general-purpose AI model provider that also offers an API or app is `limited`: Article 50(2)
    covers "general-purpose AI systems".
  - The new prohibition in point (ba) applies from 2 December 2026 but is part of the Act in force;
    it is labeled `prohibited` only.
- A label is a reading of the Act's text by a non-lawyer, not legal advice. Open points are in
  `docs/legal-sources.md`.

## Running it

Start the server, then run the script against it:

```
DO_NOT_TRACK=1 .venv/bin/python -m uvicorn app.main:app --port 7861
DO_NOT_TRACK=1 .venv/bin/python eval/run_eval.py --base-url http://127.0.0.1:7861 --out eval/results/run-1.json
```

If a run stops on `quota`, continue it the next day with the same file:

```
DO_NOT_TRACK=1 .venv/bin/python eval/run_eval.py --base-url http://127.0.0.1:7861 --out eval/results/run-1.json --resume
```

Options:

| Option | Default | Meaning |
| --- | --- | --- |
| `--base-url` | `http://127.0.0.1:7861` | server to test |
| `--limit N` | all | first N cases only |
| `--ids a,b` | all | only these case ids |
| `--sleep S` | 5 | seconds between calls (the free Gemini tier has a per-minute limit) |
| `--out PATH` | `eval/results/<timestamp>.json` | results file, written after every case |
| `--resume` | off | keep the completed cases in `--out` and run the rest; refused if the server's model, text version or fake flag differ from the earlier run |
| `--timeout S` | 180 | seconds per request |
| `--max-retries N` | 6 | retries after `rate_limited` or `quota` |
| `--backoff S`, `--max-backoff S` | 20, 300 | first wait and cap; the wait doubles, `Retry-After` wins when sent |

The script calls `POST /api/screen` with `accepted_terms: true` and reads the event stream until the
`result` or `error` event. When `rate_limited` or `quota` persists after the retries, the run stops,
marks the remaining cases `not_run` and prints the `--resume` command. With the real model, mind the
server limits (`RATE_LIMIT_PER_MIN`, `RATE_LIMIT_PER_DAY`, `DAILY_BUDGET`): 52 cases need 52 calls.

## Metrics

- Class accuracy, strict (`expected_class`) and lenient (any of `acceptable_classes`). A result
  with `in_scope: false` counts as the class `out_of_scope`; otherwise its `risk_class` counts,
  including `not_covered`.
- Per class precision, recall and F1 against `expected_class`, and the confusion matrix, with a row and a column for each of the seven classes.
- Out-of-scope detection: precision and recall of `out_of_scope`, with the ids of false positives.
- `gpai` flag: accuracy over all cases and recall over the two `gpai: true` cases.
- Expected refs: the share of cases with `expected_refs` where at least one cited unit
  (`art-6` for `art-6-3`) matches an expected unit, and a stricter part-level share.
- Quote verification: verified citations over all citations in the steps and obligations.
- Latency: mean, median and p95 seconds per call, retries included.
- Lenient accuracy by language.

The script prints a Markdown summary (two small tables) that can be pasted into the README as is.

The results file holds:
- `meta`: server, `model` and `text_version` (from `/api/health`; `text_version` falls back to the
  local `corpus.json` when the server does not report it), `date`, `fake_llm`, start and finish
  times, resume times, the full `/api/health` answer, and `summary_markdown`;
- `metrics`;
- `cases`: one row per case (prediction, `high_risk_basis`, cited refs, citation counts, latency, retries, error).
  The model's text is not stored.

## Fake mode

With `SCREENER_FAKE_LLM=1` the server classifies by keyword rules. The script prints
`FAKE MODE`, the summary says "fake mode, not real scores" and the results file has
`fake_llm: true`. Those numbers test the pipeline, not the screener; never report them as scores,
and keep fake-mode results out of the repository.
