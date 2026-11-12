# HTTP API

The app is one FastAPI process. All routes answer JSON unless noted. Version `1.0.0`.

The Act text is the consolidated version of 27 July 2026 published by EUR-Lex (Regulation (EU) 2024/1689 with the changes of Regulation (EU) 2026/1744). A consolidated text is a documentation tool without legal effect; the authentic text is the one in the Official Journal. Recitals come from the Official Journal version of 2024, because the consolidated version does not reproduce them. Every page link points into the PDF its unit comes from: `<pdf_url>#page=<n>`.

## Errors

Outside a stream every error has the same shape:

```json
{"error": {"code": "invalid_input", "message": "The description must be 30 to 4000 characters long."}}
```

| Code | Status | When |
| --- | --- | --- |
| `invalid_input` | 400, 405, 413 | Bad JSON, a field out of range, a body over 64 KB (413) |
| `terms_required` | 403 | `accepted_terms` is not the JSON value `true` (`"true"`, `1` or a missing field count as not accepted) |
| `rate_limited` | 429 | Per-IP limit per minute or per day, the global per-minute limit, the search limit or the report limit; `Retry-After` gives the seconds to wait (60 for a minute limit, the seconds to the next UTC midnight for the daily limit, whose message says to come back tomorrow) |
| `busy` | 429 | Too many screenings and questions running at once (`MAX_CONCURRENT_LLM`); message "The server is busy with other screenings. Try again in a moment." |
| `invalid_signature` | 400 | `/api/report` got a result without a valid signature of this server process, or with another description |
| `quota` | 503 | The app's daily budget is used up (`Retry-After`: seconds to the next UTC midnight); inside a stream: every model is out of quota |
| `not_configured` | 503 | No Gemini key, no corpus, no timeline or no search index |
| `llm_error` | 500 or in a stream | The model failed, the stream passed `SCREEN_DEADLINE`, or an unexpected server error |
| `not_found` | 404 | Unknown route, a missing static file, an unknown article, annex or recital, or `/disclaimer` without `DISCLAIMER.md` |

Messages are fixed sentences. They never repeat what the user sent.

## Routes

### `GET /`

The page (`app/static/index.html`). `GET /static/*` serves the rest of the frontend. `HEAD /` answers like `GET` without a body.

The page, scripts and styles carry `Cache-Control: no-cache` (checked against their ETag on every load); fonts carry `Cache-Control: public, max-age=604800` and the type `font/woff2`. The development fixtures (`app/static/fixtures/`) are not in the Docker image: there `/static/fixtures/*` answers 404 `not_found`.

### `GET /disclaimer`

The full disclaimer, the repository's `DISCLAIMER.md`, as `text/plain; charset=utf-8`. Read once at start; 404 `not_found` when the file is missing. `HEAD` works too.

### `GET /api/health`

`HEAD /api/health` answers 200 without a body, for uptime monitors.

```json
{"status": "ok", "version": "1.0.0", "llm_ready": true, "fake_llm": false, "model": "gemini-3.5-flash-lite",
 "units": 313, "corpus": true, "text_version": "Consolidated text of 27 July 2026", "retrieval": "hybrid",
 "timeline": true, "obligations": true}
```

- `llm_ready`: a Gemini key is set, or fake mode is on.
- `model`: the first model of the chain, or `fake`.
- `units`: number of units in the corpus, 0 without one.
- `text_version`: short name of the text the corpus holds, null without a corpus.
- `retrieval`: `hybrid` (BM25 and dense vectors), `keyword` (BM25 only, no usable `chroma_db`), `none` (no search).
- `timeline`, `obligations`: the data files load.

### `GET /api/examples`

```json
[{"id": "cv-screening", "title": "CV screening tool", "description": "...", "role": "provider", "expected": "high"}]
```

Eight examples. `expected` is the class the example is written to produce.

### `GET /api/timeline`

The content of `data/timeline.json`: `as_of`, `law_in_force`, `entries` (sorted by date) and `notes`.

Entry: `id`, `date` (ISO), `label`, `detail`, `applies_to`, `source_ref`, `sources` (`title`, `url`).

`applies_to` values:

| Value | Shown on a screening result when |
| --- | --- |
| `all` | always, except for `not_covered` and for a `high` result with basis `annex_i_section_b` |
| `prohibited`, `high`, `limited`, `minimal`, `unclear` | `risk_class` is that class (not `high` with basis `annex_i_section_b`) |
| `high_annex_iii` | class `high` and `high_risk_basis` is `annex_iii`, `both` or `none` |
| `high_annex_i` | class `high` and `high_risk_basis` is `annex_i`, `both` or `none` |
| `high_annex_i_b` | class `high` and `high_risk_basis` is `annex_i_section_b`; the only tag such a result shows, besides `gpai` |
| `generative` | the obligation `prevent-prohibited-content` is listed |
| `gpai` | `gpai.applies` is true |
| `public_authority`, `large_scale_it` | never; these are only in this route |

A `not_covered` result shows no entry. An entry whose `source_ref` is Article 50 or one of its paragraphs is shown only when the transparency step is `yes`.

### `GET /api/source`

The `source` block of `data/corpus.json`: `title`, `celex`, `eli`, `consolidated_version`, `includes` (the amending acts), `pdf_url`, `html_url`, `legal_notice` (EUR-Lex's notice on consolidated texts) and `recitals` (where the recitals come from, with their own `pdf_url`).

### `GET /api/toc`

```json
{"chapters": [{"number": "I", "title": "...", "articles": [{"id": "art-1", "number": "1", "title": "...", "section": null,
   "section_title": null, "amended": false}]}],
 "annexes": [{"id": "annex-I", "number": "I", "title": "...", "amended": true}], "recitals": {"count": 180}}
```

### `GET /api/unit/{ref}`

`ref` is a unit id (`art-6`, `art-4a`, `annex-III`, `rec-53`), a part id (`art-6-3`, `art-6-1a`, `annex-III-4`) or a readable form (`Article 6(3)`).

```json
{"id": "art-6", "kind": "article", "number": "6", "label": "Article 6", "title": "...",
 "chapter": "III", "chapter_title": "...", "section": "1", "section_title": "...",
 "page_start": 17, "page_end": 19, "page_url": "https://eur-lex.europa.eu/...#page=17",
 "pdf_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02024R1689-20260727", "amended": true, "text": "...",
 "parts": [{"id": "art-6-1", "label": "1", "text": "...", "page": 17, "amended": false}],
 "prev": "art-5", "next": "art-7", "focus": "art-6-3"}
```

A part id returns its unit with `focus` set to the part; a unit id gives `focus: null`.
`page_start` and `page_url` are the unit's first page; the page of a part is its own `page` (for the focused part, `parts[].page` of the part whose `id` is `focus`).
A `ref` longer than 64 characters answers 404 `not_found`.
An id that names a part that does not exist (`art-6-99`, `annex-III-99`) answers 404 `not_found`; a readable form is resolved by the corpus as well as it can.
`amended` is true when Regulation (EU) 2026/1744 changed or inserted that unit or part. `pdf_url` is the PDF the unit's text and pages come from.

### `GET /api/search?q=...&k=20&kind=article`

- `q`: 1 to 300 characters. `k`: 1 to 50, default 20. `kind`: `article`, `annex` or `recital`, optional.
- Hybrid search when `retrieval` is `hybrid`, BM25 only when it is `keyword`. No LLM call.
- Relevance floor: `hits` is an empty list when the query does not match the Act. Hybrid: the best dense match has a cosine similarity below 0.28 and fewer than 65 percent of the query's words (after stop words, with the glossary expansion) occur in the Act. Keyword: fewer than 65 percent of the words occur in the Act. A query that passes gets up to `k` hits as before.

```json
{"query": "...", "hits": [{"ref": "art-50-1", "unit_id": "art-50", "kind": "article", "label": "Article 50(1)",
  "title": "...", "snippet": "...", "page": 82, "page_url": "...", "score": 0.031}]}
```

### `POST /api/screen`

```json
{"description": "30 to 4000 characters", "role": "provider",
 "answers": [{"question": "...", "answer": "..."}], "accepted_terms": true}
```

- `role`: `provider`, `deployer` or `unknown` (default).
- `answers`: at most 10; question up to 500, answer up to 1000 characters. The answers are cleaned like the description (see "What goes into the prompt"); a pair whose answer is empty after that is dropped. The cleaned list goes into the prompt and comes back as `answers` in the result.

The answer is `text/event-stream`:

```
event: stage
data: {"stage":"retrieving"}

event: stage
data: {"stage":"reasoning"}

event: stage
data: {"stage":"verifying"}

event: result
data: {ScreenResult}
```

The result carries `signature`, a hex HMAC-SHA256 that `/api/report` checks (see there).

On failure the stream ends with `event: error` and `data: {"code": "...", "message": "..."}`.
Checks before the stream (terms, configuration, limits) answer with a JSON error instead.
The whole stream has one deadline, `SCREEN_DEADLINE` seconds; past it the model call is cancelled and the stream ends with `error` code `llm_error`.

### `POST /api/ask`

```json
{"question": "5 to 1000 characters", "history": [{"role": "user", "content": "..."}], "accepted_terms": true}
```

- `history`: at most 6 items, `role` is `user` or `assistant`, content up to 4000 characters; each item is cut to 1500 characters in the prompt.
- The search for sources uses the question (with the last earlier user question before it). A question below the search floor (see `/api/search`) gets no sources; the model is then told that the sources are empty.

Stream:

```
event: sources
data: {"citations": [{"ref": "...", "label": "Article 6(3)", "title": "...", "page": 54, "page_url": "..."}]}

event: token
data: {"text": "..."}

event: done
data: {}
```

The answer cites with markers such as `[Article 6(3)]` that match a source `label`.
The same deadline as `/api/screen` applies to the whole stream.

### `POST /api/report`

```json
{"description": "...", "result": {ScreenResult}}
```

- `result`: the ScreenResult exactly as the `result` event of `/api/screen` sent it, `signature` included. Any changed character, a missing signature, or a result from before a server restart answers 400 `invalid_signature`.
- `description`: the description exactly as it was screened (leading and trailing whitespace is ignored on both sides). The answers need not be sent again: they are in the signed `result`.
- Signature: HMAC-SHA256, hex, keyed with `REPORT_SECRET` (or 32 random bytes made at process start), over the canonical JSON of the result without `signature` (keys sorted, separators `,` and `:`, UTF-8, non-ASCII characters not escaped), a newline, and the SHA-256 hex of the description. The comparison runs in constant time.
- The body cap of 64 KB applies: a result larger than that cannot be reported (413 `invalid_input`).
- Per-IP limit `REPORT_LIMIT_PER_MIN`; above it `rate_limited`.

Answers `text/markdown; charset=utf-8` with `Content-Disposition: attachment; filename="eu-ai-act-screening.md"`.

The report escapes every string the model or the user wrote for Markdown and HTML, and builds no link from them. Labels, titles, page links, the verification marks ("found word for word in the cited text"; for a recital, "of the 2024 Official Journal version"), the counts, the text version and the disclaimer are rebuilt on the server from the corpus and the citation flags. The description is a quoted block; the answers follow under "Answers given by the user", one numbered question and answer each.

The class names match the page: "Prohibited practice", "High-risk system" (with the route: "Annex III use", "Annex I product (Section A)", "Annex I product (Section B)", "Annex I and Annex III"), "Limited risk", "Minimal risk", "Outside the Act", "Unclear". Each obligation shows its `condition` ("Only when: ...") and `amended` line. A date reads "In force" or "Applies now" when it has passed, else "In force from" or "Applies from" the date, as on the page. The role `unknown` reads "Not sure"; the report date is the UTC date of `created`.

## ScreenResult

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | UUID4 of this result |
| `created` | string | UTC time, `2026-11-11T20:00:00Z` |
| `model` | string | Model that answered, or `fake` |
| `version` | string | App version |
| `text_version` | string | The text the quotes were checked against, for example `Consolidated text of 27 July 2026` |
| `in_scope` | bool | False when the text is not a description of an AI system, or tries to instruct the model |
| `refusal` | string or null | One sentence when `in_scope` is false; at most 300 characters |
| `language` | string | ISO 639-1 code of the description |
| `summary` | string | The system as the model understood it; at most 600 characters |
| `risk_class` | string | `prohibited`, `high`, `limited`, `minimal`, `not_covered`, `unclear` (see below) |
| `confidence` | string | `low`, `medium`, `high`; set to `low` when the backend corrected the path |
| `headline` | string | The deciding reason in one sentence; at most 300 characters; a fixed sentence when the backend changed the class, in the result's `language` for `en`, `nl`, `fr`, `de` and `tr`, else English |
| `role` | string | `provider`, `deployer`, `unknown`; the stated role wins over the inferred one |
| `high_risk_basis` | string | `annex_i` (Annex I Section A), `annex_i_section_b`, `annex_iii`, `both` (Section A and Annex III), `none` (none unless the high-risk step is `yes`) |
| `gpai` | object | `applies` (bool, true only when the general-purpose AI step is `yes`), `note` (string or null, at most 300 characters) |
| `steps` | list | Always six, in this order: `scope`, `prohibited`, `high_risk`, `exemption`, `transparency`, `gpai` |
| `obligations` | list | Items of `data/obligations.json` only; the model picks ids, every text comes from the file |
| `open_questions` | list | `question`, `why` (each at most 300 characters); at most 5 |
| `deadlines` | list | From `data/timeline.json`, see the `applies_to` table |
| `verification` | object | `total` quotes, `verified` quotes |
| `sources` | list | Unique cited refs: `ref`, `label`, `title`, `page`, `page_url` |
| `answers` | list | `question`, `answer`: the user's answers this screening used, cleaned as they went into the prompt; empty without answers. Part of the signed result |
| `disclaimer` | string | Fixed text; names the checked text and that a consolidated text has no legal effect |
| `signature` | string | Added by the server to the streamed result; see `/api/report` |

Step: `id`, `title`, `question` (fixed English text), `outcome` (`yes`, `no`, `unclear`, `not_applicable`), `reasoning` (at most 1200 characters from the model, plus a fixed note when the backend changed the outcome), `citations` (at most 4).

Citation: `ref`, `label`, `title`, `quote`, `verified`, `page`, `page_url`.
`quote` and `verified` are null on an obligation reference, and absent in `/api/ask` sources.
A quote with an ellipsis is split into its continuous segments; each segment is its own citation. A verified citation shows the passage exactly as it stands in the corpus text, and its `ref` may move to another part of the same unit where the passage was found. A quote that is not found stays, with the model's words and `verified: false`. At most 16 quoted citations per result.

Obligation: `id` (menu id), `title`, `detail`, `who` (`provider`, `deployer`, `both`), `citation` (the menu item's ref, or null), `condition` (string or null: the duty applies only in this case), `amended` (string or null: how Regulation (EU) 2026/1744 changed it). Every field comes from `data/obligations.json`.

Deadline: `id`, `date`, `label`, `detail`, `status` (`in_force` when the date is today or earlier, else `upcoming`), `source_ref`, `source_label`, `page_url`.

Classes:

| `risk_class` | Meaning |
| --- | --- |
| `prohibited` | An Article 5 practice |
| `high` | Article 6(1) with Annex I (Section A or B) or Article 6(2) with Annex III, without the Article 6(3) exemption |
| `limited` | Not prohibited, not high-risk (or exempted), and Article 50 applies |
| `minimal` | The Act applies, and none of Article 5, Article 6 and Article 50 does |
| `not_covered` | A system description to which the Act does not apply: not an AI system under Article 3(1), or an Article 2 exclusion |
| `unclear` | The answer does not allow a decision |

Rules the backend enforces on the model's answer:

- A citation whose ref was not in the context sent to the model is dropped.
- Every step is present once. A missing step becomes `unclear`; for a step given twice, the more severe reading wins (for the exemption, the reading that keeps the system high-risk). Both set `confidence` to `low`.
- A step the path reaches is never `not_applicable`; the backend makes it `unclear`. Steps the path does not reach become `not_applicable`.
- Scope `no`: `not_covered`, steps 2 to 6 `not_applicable`, no obligations, no dates. Scope `no` together with a `yes` on step 2, 3 or 5 is a contradiction: scope becomes `unclear`, an open question is added, and the later steps decide.
- Prohibited `yes`: `prohibited`, steps 3 to 5 `not_applicable`.
- The Article 6(3) exemption only applies to the Annex III route: `not_applicable` for `annex_i` and `annex_i_section_b`, `no` for `both` (the Annex I route keeps the system high-risk), `unclear` with an open question for `none`. With profiling of natural persons it is `no`; when profiling is unclear it is `unclear` and an open question is added. The class is then `high`.
- Basis `annex_i_section_b`: the transparency step is `not_applicable` and the obligations come from the group `high_annex_i_b` (Article 2(2)).
- `minimal` needs the explicit path: scope `yes`, prohibited `no`, high-risk `no` (or `yes` through Annex III with the exemption `yes` and no profiling), transparency `no`. Anything short of a decided path is `unclear`, or the more severe class when a step says so. Scope `unclear` never makes the class `unclear` on its own when a later step decides a class, because it could only lead to `not_covered`.
- `risk_class` follows the step outcomes; when it differs from the class the model wrote, the headline is replaced by a fixed sentence in the language of the result (English for a language other than en, nl, fr, de, tr).
- A high-risk result through `annex_i` or `annex_i_section_b` drops open questions that name Article 6(3): the exemption cannot apply to that route.
- The Article 6(4) documentation and Article 49(2) registration duty is listed for a provider only when the class is `minimal` or `limited` because of the exemption.
- Obligations: only menu ids of the result's groups (the class, `high_annex_i_b` instead of `high` for Section B, `limited` when the transparency step is `yes`, `gpai` when `gpai.applies`); none for `unclear` and `not_covered`.
- Text written by the model: control, format and zero-width characters removed, long dashes replaced, length capped at a word boundary, and every explicit calendar date (for example `2 August 2026`, `August 2, 2026`, `2026-08-02`, `02/08/2026`, also in Dutch, French, German and Turkish) replaced by "the date shown under Dates that apply". Article, paragraph and act numbers stay. HTML and Markdown are passed as text; the page escapes them.
- When `in_scope` is false: `risk_class` is `unclear`, all steps are `not_applicable`, and the lists are empty.

What goes into the prompt: the obligations menu as `id: title` lines (with "Only when:" and the condition where one is set) under a `[group / role]` header; detail and amendment texts stay out, because the result takes them from the data file. The description, the answers, the ask question and the ask history are NFKC-normalized, control and zero-width characters are removed, and anything that reads as a tag (`<...>`, in any width or look-alike bracket) or as a context header (`[ref: ...]`, `[amended]`) is turned into plain parentheses. The user's text sits between delimiters that carry a random token per request. `/api/ask` never passes earlier turns as model turns: they go into the user message as quoted, labeled text.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `GOOGLE_API_KEY` | none | Gemini key. Without it the reader and search work; screen and ask answer `not_configured` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | First model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.1-flash-lite,gemini-2.5-flash-lite` | Tried in order when a model is not found, out of quota, failing or timing out |
| `GEMINI_THINKING_LEVEL` | `low` | `minimal`, `low`, `medium` or `high` for Gemini 3 and later; `none`, `off` or `default` leave the model default; any other value is read as `low` |
| `LLM_TIMEOUT` | `60` | Seconds per model call, capped at 45 (a higher value counts as 45); a streamed answer has at most 90 seconds in all |
| `SCREENER_FAKE_LLM` | `0` | `1`: no model call, a deterministic result from keyword rules |
| `SCREENER_FAKE_DELAY` | `0.4` | Seconds between stages in fake mode |
| `SCREENER_WARMUP` | `1` | Load the corpus and the search index at start |
| `RATE_LIMIT_PER_MIN` | `6` | Screen and ask requests per client IP per minute |
| `RATE_LIMIT_PER_DAY` | `60` | Screen and ask requests per client IP per UTC day |
| `DAILY_BUDGET` | `900` | Screen and ask requests for the whole app per UTC day |
| `GLOBAL_RATE_PER_MIN` | `20` | Screen and ask requests for the whole app per minute, on top of the per-IP limits; `0` turns it off |
| `MAX_CONCURRENT_LLM` | `4` | Screenings and questions running at once; above it `busy` |
| `SCREEN_DEADLINE` | `120` | Seconds for a whole screen or ask stream |
| `SEARCH_LIMIT_PER_MIN` | `60` | Searches per client IP per minute |
| `REPORT_LIMIT_PER_MIN` | `20` | Reports per client IP per minute |
| `REPORT_SECRET` | random per process | Key that signs results for `/api/report`; set it so reports keep working after a restart |
| `TRUSTED_PROXY_HOPS` | `1` | Proxies in front of the app that append to `X-Forwarded-For`; `0` ignores the header. Set `0` when nothing sits in front of the app: with `1` and no proxy, a client can pick its own rate-limit key with a forged header |
| `PORT` | `7860` | Read into the settings; the Docker image starts uvicorn on 7860 |
| `FASTEMBED_CACHE_PATH` | `models/` | Where the embedding model is cached (retrieval) |
| `EMBED_THREADS` | library default | Threads for the embedding model (retrieval) |

The client address is counted from the right of `X-Forwarded-For`: with `TRUSTED_PROXY_HOPS` = N it is the N-th address from the right (with 1, the last one); everything to its left is written by the client and ignored. With 0, a header shorter than N entries, or an address that does not parse, the socket address is used. IPv4-mapped IPv6 addresses count as IPv4, and an IPv6 client is keyed by its /64.
A request whose stream ends before the model is called is not counted against the limits.
The access log carries no client address and no query string.
