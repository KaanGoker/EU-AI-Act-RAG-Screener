# Changelog

## v1.0

### For users

- New web page in place of the Chainlit chat: a form for the description and your role, a progress view, and the result on one page, in light and dark, on desktop and phone.
- A decision path of six checks (scope, prohibited practices, high-risk, Article 6(3) exemption, transparency, general-purpose AI), each with its outcome, reasoning and quotes.
- Six result classes: prohibited, high-risk, limited risk, minimal risk, outside the Act, unclear.
- Every quote is checked against the cited provision and marked as verified or not found.
- Obligations for providers and deployers, and the dates that apply, each with its article.
- Open questions that can be answered to screen again.
- The whole Act in a reader beside the result, with search, a table of contents, the quoted words highlighted, the 2026 changes marked and page links to the EUR-Lex PDF.
- Ask the Act: questions about the Act, answered with citations.
- Markdown report and a print layout.
- The text is now the consolidated version of 27 July 2026, with the amendments of Regulation (EU) 2026/1744 (Digital Omnibus on AI).

### Inside

- FastAPI app with a plain HTML, CSS and JavaScript page; Chainlit, the old `chainlit_app.py` and `ingest.py` are gone.
- The Act is parsed by structure into 313 units with paragraphs, points and page numbers (`ingest/build_corpus.py`).
- Hybrid search: BM25 and local fastembed vectors (EmbeddingGemma 300M) in ChromaDB, merged with reciprocal rank fusion. No API call for search or indexing.
- One Gemini call with structured output per screening, with fallback models.
- The class is derived by fixed rules from the step outcomes; obligations come from `data/obligations.json` and dates from `data/timeline.json`.
- Signed results for the report, per-IP and global rate limits, a daily budget, and no logging of user text.
- 488 tests, a retrieval evaluation with 69 queries and an evaluation set of 52 labeled cases.
- First run against the live Space with `gemini-3.5-flash-lite`: 84.6% class accuracy (44 of 52) and 273 of 285 quotes found in the cited text (see `eval/RESULTS.md`).
- Docker image for a Hugging Face Docker Space.
