# Evaluation results

One run of `eval/run_eval.py` over the 52 cases in `cases.jsonl`, against the live Hugging Face Space.

- Date: 12 November 2026 (00:45 to 01:03 UTC)
- App version: 1.0.0
- Model: `gemini-3.5-flash-lite`; one case (`hr-warehouse-monitoring`) was answered by the fallback model `gemini-3.1-flash-lite`
- Act text: consolidated text of 27 July 2026
- Server: the Space on the free CPU hardware, called from outside, 11 seconds between calls
- No errors and no retries

## Summary

| Metric | Value |
| --- | --- |
| Cases completed | 52 of 52 |
| Class accuracy, strict | 84.6% (44 of 52) |
| Class accuracy, acceptable classes | 84.6% |
| Out of scope, precision / recall | 100.0% / 100.0% |
| General-purpose AI flag, accuracy | 100.0% |
| Expected article cited | 96.0% |
| Quotes found in the cited text | 273 of 285 (95.8%) |
| Latency per screening, mean / median / p95 | 9.2 s / 8.9 s / 12.4 s |

## Per class

| Expected class | Precision | Recall | Cases |
| --- | --- | --- | --- |
| prohibited | 88.9% | 88.9% | 9 |
| high | 71.4% | 93.8% | 16 |
| limited | 100.0% | 88.9% | 9 |
| minimal | 87.5% | 77.8% | 9 |
| not_covered | 100.0% | 100.0% | 3 |
| unclear | 100.0% | 25.0% | 4 |
| out_of_scope | 100.0% | 100.0% | 2 |

- By difficulty: easy 16 of 16, medium 14 of 18, hard 14 of 18.
- Non-English cases: 7 of 8 (Dutch 2 of 2, French 2 of 2, Turkish 2 of 2, German 1 of 2).

## The eight misses

| Case | Language | Expected | Predicted |
| --- | --- | --- | --- |
| `pr-emotion-callcenter-staff` | German | prohibited | high |
| `le-reoffending-risk` | English | high | prohibited |
| `gpai-open-weights-llm` | English | limited | minimal |
| `min-face-unlock-gym` | English | minimal | high |
| `min-duplicate-applications` | English | minimal | high |
| `unc-people-scoring` | English | unclear | high |
| `unc-student-essays` | English | unclear | high |
| `unc-voice-emotion-calls` | English | unclear | high |

Five of the eight are descriptions that are underspecified or sit on a border, which the model placed in high-risk instead of unclear or minimal. Only 1 of the 4 unclear cases came back as unclear.

## Limits

- 52 cases is a small set; one case moves the accuracy by about 2 points.
- The labels are my own reading of the Act; no lawyer has reviewed them. Open points are in `docs/legal-sources.md`.
- This is one run of one model on one date. No second run was made, so how much the results change between runs is not measured.

## How to reproduce

```
DO_NOT_TRACK=1 .venv/bin/python eval/run_eval.py --base-url https://kaangoker-eu-ai-act-rag-screener-demo.hf.space --sleep 11 --out eval/results/live-v2.0.json
```

The results file itself stays out of the repository (`eval/results/` is ignored).
