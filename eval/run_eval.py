"""Run the labeled cases through a running screener server and score the results.

    .venv/bin/python eval/run_eval.py --base-url http://127.0.0.1:7861 --out eval/results/run.json

Only the standard library and httpx. The server can run in fake mode or with the real model;
the results file records which one (from /api/health), and fake-mode scores are not real scores.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases.jsonl"
CLASSES = ["prohibited", "high", "limited", "minimal", "not_covered", "unclear", "out_of_scope"]
RETRY_CODES = {"rate_limited", "quota"}
UNIT_RE = re.compile(r"^(art-\d+[a-z]?|annex-[ivxlc]+|rec-\d+)", re.IGNORECASE)


class Retryable(Exception):
    def __init__(self, code: str, wait: float | None = None):
        super().__init__(code)
        self.code = code
        self.wait = wait


def norm_ref(ref: str) -> str:
    """Lower case except the roman numeral of an annex: annex-iii-4 -> annex-III-4."""
    ref = (ref or "").strip()
    m = re.match(r"^annex-([ivxlc]+)(.*)$", ref, re.IGNORECASE)
    if m:
        return "annex-" + m.group(1).upper() + m.group(2).lower()
    return ref.lower()


def unit_of(ref: str) -> str:
    m = UNIT_RE.match(norm_ref(ref))
    return norm_ref(m.group(1)) if m else norm_ref(ref)


def part_match(cited: str, expected: str) -> bool:
    """A cited ref matches an expected ref if it is the same or lies inside it (art-6-3 inside art-6)."""
    c, e = norm_ref(cited), norm_ref(expected)
    return c == e or c.startswith(e + "-")


def load_cases(path: Path) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                sys.exit(f"{path}:{n}: {exc}")
    return cases


def parse_sse(lines) -> list[tuple[str, str]]:
    """Collect (event, data) pairs from an event stream."""
    events, name, data = [], "message", []
    for raw in lines:
        line = raw.rstrip("\r")
        if line == "":
            if data:
                events.append((name, "\n".join(data)))
            name, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        events.append((name, "\n".join(data)))
    return events


def screen_once(client: httpx.Client, base: str, case: dict, timeout: float) -> dict:
    body = {"description": case["description"], "role": case.get("role", "unknown"), "answers": [], "accepted_terms": True}
    with client.stream("POST", base + "/api/screen", json=body, timeout=timeout) as resp:
        if resp.status_code != 200:
            resp.read()
            try:
                err = resp.json().get("error", {})
            except ValueError:
                err = {}
            code = err.get("code") or f"http_{resp.status_code}"
            if code in RETRY_CODES or resp.status_code == 429:
                wait = resp.headers.get("Retry-After")
                raise Retryable(code, float(wait) if wait and wait.replace(".", "", 1).isdigit() else None)
            return {"error": code, "message": err.get("message")}
        events = parse_sse(resp.iter_lines())
    for name, data in events:
        if name == "error":
            try:
                err = json.loads(data)
            except ValueError:
                err = {"code": "bad_error_event"}
            if err.get("code") in RETRY_CODES:
                raise Retryable(err["code"])
            return {"error": err.get("code") or "error", "message": err.get("message")}
        if name == "result":
            try:
                return {"result": json.loads(data)}
            except ValueError:
                return {"error": "bad_result_json"}
    return {"error": "no_result_event"}


def screen(client: httpx.Client, base: str, case: dict, args) -> tuple[dict, float, int]:
    """Call the API with retries on rate_limited and quota. Returns (outcome, seconds, retries)."""
    delay = args.backoff
    for attempt in range(args.max_retries + 1):
        start = time.monotonic()
        try:
            out = screen_once(client, base, case, args.timeout)
            return out, time.monotonic() - start, attempt
        except Retryable as exc:
            if attempt == args.max_retries:
                return {"error": exc.code}, time.monotonic() - start, attempt
            wait = exc.wait if exc.wait is not None else delay
            print(f"  {exc.code}: waiting {wait:.0f} s (retry {attempt + 1}/{args.max_retries})", flush=True)
            time.sleep(wait)
            delay = min(delay * 2, args.max_backoff)
        except httpx.HTTPError as exc:
            return {"error": f"transport: {type(exc).__name__}"}, time.monotonic() - start, attempt
    return {"error": "unreachable"}, 0.0, args.max_retries


def citations_of(result: dict) -> list[dict]:
    cites = []
    for step in result.get("steps") or []:
        cites.extend(c for c in step.get("citations") or [] if isinstance(c, dict))
    for ob in result.get("obligations") or []:
        c = ob.get("citation")
        if isinstance(c, dict) and c.get("quote"):
            cites.append(c)
    return cites


def predicted_class(result: dict) -> str:
    """in_scope false is out_of_scope; otherwise the risk_class, including not_covered."""
    if result.get("in_scope") is False:
        return "out_of_scope"
    return result.get("risk_class") or "unclear"


def score_case(case: dict, outcome: dict, latency: float, retries: int) -> dict:
    row = {
        "id": case["id"], "lang": case.get("lang"), "difficulty": case.get("difficulty"),
        "expected": case["expected_class"], "acceptable": case.get("acceptable_classes") or [case["expected_class"]],
        "gpai_expected": bool(case.get("gpai")), "expected_refs": case.get("expected_refs") or [],
        "latency_s": round(latency, 3), "retries": retries, "error": outcome.get("error"),
    }
    result = outcome.get("result")
    if result is None:
        row.update(predicted=None, strict_ok=False, lenient_ok=False, gpai_pred=None, gpai_ok=False,
                   cited_refs=[], ref_hit_unit=None, ref_hit_part=None, citations_total=0, citations_verified=0)
        return row
    pred = predicted_class(result)
    cites = citations_of(result)
    cited = sorted({norm_ref(c.get("ref", "")) for c in cites if c.get("ref")})
    exp = row["expected_refs"]
    gpai_pred = bool((result.get("gpai") or {}).get("applies"))
    row.update(
        predicted=pred,
        strict_ok=pred == case["expected_class"],
        lenient_ok=pred in row["acceptable"],
        confidence=result.get("confidence"),
        high_risk_basis=result.get("high_risk_basis"),
        model=result.get("model"),
        language=result.get("language"),
        gpai_pred=gpai_pred,
        gpai_ok=gpai_pred == row["gpai_expected"],
        cited_refs=cited,
        ref_hit_unit=(bool({unit_of(r) for r in cited} & {unit_of(e) for e in exp}) if exp else None),
        ref_hit_part=(any(part_match(c, e) for c in cited for e in exp) if exp else None),
        citations_total=len(cites),
        citations_verified=sum(1 for c in cites if c.get("verified") is True),
        server_verification=result.get("verification"),
    )
    return row


def ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def metrics(rows: list[dict]) -> dict:
    done = [r for r in rows if r["predicted"] is not None]
    n = len(done)
    confusion = {e: {p: 0 for p in CLASSES} for e in CLASSES}
    for r in done:
        p = r["predicted"] if r["predicted"] in CLASSES else "unclear"
        confusion[r["expected"]][p] += 1
    per_class = {}
    for c in CLASSES:
        tp = confusion[c][c]
        pred_c = sum(confusion[e][c] for e in CLASSES)
        true_c = sum(confusion[c].values())
        prec, rec = ratio(tp, pred_c), ratio(tp, true_c)
        f1 = round(2 * prec * rec / (prec + rec), 4) if prec and rec else (0.0 if pred_c and true_c else None)
        per_class[c] = {"precision": prec, "recall": rec, "f1": f1, "support": true_c, "predicted": pred_c}
    oos_true = [r for r in done if r["expected"] == "out_of_scope"]
    oos_pred = [r for r in done if r["predicted"] == "out_of_scope"]
    oos_tp = sum(1 for r in oos_true if r["predicted"] == "out_of_scope")
    with_refs = [r for r in done if r["ref_hit_unit"] is not None]
    total_c = sum(r["citations_total"] for r in done)
    ver_c = sum(r["citations_verified"] for r in done)
    lat = [r["latency_s"] for r in done]
    lat_sorted = sorted(lat)
    return {
        "cases": len(rows), "completed": n, "errors": len(rows) - n,
        "error_codes": sorted({r["error"] for r in rows if r["error"]}),
        "accuracy_strict": ratio(sum(r["strict_ok"] for r in done), n),
        "accuracy_lenient": ratio(sum(r["lenient_ok"] for r in done), n),
        "per_class": per_class,
        "confusion": confusion,
        "out_of_scope": {
            "precision": ratio(oos_tp, len(oos_pred)), "recall": ratio(oos_tp, len(oos_true)),
            "false_positive_ids": [r["id"] for r in oos_pred if r["expected"] != "out_of_scope"],
        },
        "gpai_accuracy": ratio(sum(r["gpai_ok"] for r in done), n),
        "gpai_recall": ratio(sum(1 for r in done if r["gpai_expected"] and r["gpai_pred"]), sum(1 for r in done if r["gpai_expected"])),
        "ref_hit_unit": ratio(sum(r["ref_hit_unit"] for r in with_refs), len(with_refs)),
        "ref_hit_part": ratio(sum(r["ref_hit_part"] for r in with_refs), len(with_refs)),
        "quote_verification": {"verified": ver_c, "total": total_c, "rate": ratio(ver_c, total_c)},
        "latency_s": {
            "mean": round(statistics.mean(lat), 3) if lat else None,
            "median": round(statistics.median(lat), 3) if lat else None,
            "p95": lat_sorted[min(len(lat_sorted) - 1, int(0.95 * len(lat_sorted)))] if lat else None,
        },
        "by_lang": {
            lang: ratio(sum(r["lenient_ok"] for r in done if r["lang"] == lang), sum(1 for r in done if r["lang"] == lang))
            for lang in sorted({r["lang"] for r in done})
        },
    }


def fmt(x) -> str:
    return "n/a" if x is None else (f"{x:.1%}" if isinstance(x, float) else str(x))


def markdown_summary(m: dict, meta: dict) -> str:
    """A small Markdown table that can be pasted into a README."""
    q, lt = m["quote_verification"], m["latency_s"]
    mode = "fake mode, not real scores" if meta.get("fake_llm") else "real model"
    rows = [
        ("Model", f"{meta.get('model')} ({mode})"),
        ("Act text", str(meta.get("text_version"))),
        ("Date", str(meta.get("date"))),
        ("Cases completed", f"{m['completed']} of {m['cases']}"),
        ("Class accuracy, strict", fmt(m["accuracy_strict"])),
        ("Class accuracy, acceptable classes", fmt(m["accuracy_lenient"])),
        ("Out of scope, precision / recall", f"{fmt(m['out_of_scope']['precision'])} / {fmt(m['out_of_scope']['recall'])}"),
        ("General-purpose AI flag, accuracy", fmt(m["gpai_accuracy"])),
        ("Expected article cited", fmt(m["ref_hit_unit"])),
        ("Quotes verified", f"{q['verified']} of {q['total']} ({fmt(q['rate'])})"),
        ("Mean latency", f"{lt['mean']} s" if lt["mean"] is not None else "n/a"),
    ]
    out = ["| Metric | Value |", "| --- | --- |"]
    out += [f"| {k} | {v} |" for k, v in rows]
    out += ["", "| Class | Precision | Recall | Cases |", "| --- | --- | --- | --- |"]
    out += [f"| {c} | {fmt(v['precision'])} | {fmt(v['recall'])} | {v['support']} |" for c, v in m["per_class"].items()]
    return "\n".join(out)


def report(m: dict, meta: dict) -> str:
    out = []
    if meta.get("fake_llm"):
        out.append("FAKE MODE: the server answered with SCREENER_FAKE_LLM=1. These are not real scores.")
    out.append(f"server {meta['base_url']}  errors {m['errors']} {m['error_codes'] or ''}")
    out.append("")
    out.append(markdown_summary(m, meta))
    out.append("")
    short = {"prohibited": "proh", "high": "high", "limited": "lim", "minimal": "min", "not_covered": "ncov", "unclear": "uncl", "out_of_scope": "oos"}
    out.append("confusion (rows expected, columns predicted)")
    out.append(" " * 6 + "".join(f"{short[c]:>6}" for c in CLASSES))
    for e in CLASSES:
        out.append(f"{short[e]:<6}" + "".join(f"{m['confusion'][e][p]:>6}" for p in CLASSES))
    return "\n".join(out)


def local_text_version() -> str | None:
    """Fallback when /api/health does not report the text version: the local corpus source."""
    try:
        src = json.loads((ROOT / "data" / "corpus.json").read_text(encoding="utf-8")).get("source", {})
    except (OSError, ValueError):
        return None
    v = src.get("consolidated_version")
    return f"consolidated version of {v} (local corpus.json)" if v else src.get("title")


def save(path: Path, meta: dict, rows: list[dict]) -> dict:
    m = metrics(rows)
    meta = {**meta, "summary_markdown": markdown_summary(m, meta)}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"meta": meta, "metrics": m, "cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return m


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:7861")
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--limit", type=int, default=None, help="run only the first N cases")
    ap.add_argument("--ids", default=None, help="comma-separated case ids")
    ap.add_argument("--sleep", type=float, default=5.0, help="seconds between calls (default 5)")
    ap.add_argument("--out", type=Path, default=None, help="results file, default eval/results/<timestamp>.json")
    ap.add_argument("--resume", action="store_true", help="continue the run in --out: keep completed cases, redo the rest")
    ap.add_argument("--timeout", type=float, default=180.0, help="seconds per request")
    ap.add_argument("--max-retries", type=int, default=6)
    ap.add_argument("--backoff", type=float, default=20.0, help="first wait after rate_limited or quota")
    ap.add_argument("--max-backoff", type=float, default=300.0)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    cases = load_cases(args.cases)
    if args.ids:
        wanted = [i.strip() for i in args.ids.split(",") if i.strip()]
        known = {c["id"] for c in cases}
        missing = [i for i in wanted if i not in known]
        if missing:
            sys.exit(f"unknown case ids: {', '.join(missing)}")
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit is not None:
        cases = cases[: args.limit]

    started = datetime.now(timezone.utc)
    if args.resume and not args.out:
        sys.exit("--resume needs --out pointing to the results file of the earlier run")
    out_path = args.out or ROOT / "eval" / "results" / f"{started.strftime('%Y%m%d-%H%M%S')}.json"

    previous: dict[str, dict] = {}
    old_meta: dict = {}
    if args.resume and out_path.exists():
        old = json.loads(out_path.read_text(encoding="utf-8"))
        old_meta = old.get("meta", {})
        previous = {r["id"]: r for r in old.get("cases", []) if r.get("predicted") is not None}

    with httpx.Client() as client:
        try:
            health = client.get(base + "/api/health", timeout=30).json()
        except (httpx.HTTPError, ValueError) as exc:
            sys.exit(f"cannot reach {base}/api/health: {exc}")
        meta = {
            "base_url": base,
            "date": started.date().isoformat(),
            "started": started.isoformat(timespec="seconds"),
            "model": health.get("model"),
            "text_version": health.get("text_version") or local_text_version(),
            "fake_llm": bool(health.get("fake_llm")),
            "health": health,
            "cases_file": str(args.cases),
            "sleep_s": args.sleep,
        }
        if old_meta:
            for key in ("model", "fake_llm", "text_version"):
                if old_meta.get(key) != meta[key]:
                    sys.exit(f"cannot resume: {key} was {old_meta.get(key)!r}, server now reports {meta[key]!r}")
            meta["started"] = old_meta.get("started", meta["started"])
            meta["date"] = old_meta.get("date", meta["date"])
            meta["resumed"] = old_meta.get("resumed", []) + [started.isoformat(timespec="seconds")]
            print(f"resuming: {len(previous)} completed cases kept from {out_path}")
        if meta["fake_llm"]:
            print("FAKE MODE: the server runs with SCREENER_FAKE_LLM=1. Scores from this run are not real scores.")

        rows: list[dict] = []
        todo = [c for c in cases if c["id"] not in previous]
        stopped = None
        done_calls = 0
        for i, case in enumerate(cases, 1):
            if case["id"] in previous:
                rows.append(previous[case["id"]])
                continue
            if stopped:
                rows.append(score_case(case, {"error": "not_run"}, 0.0, 0))
                continue
            if done_calls and args.sleep > 0:
                time.sleep(args.sleep)
            outcome, latency, retries = screen(client, base, case, args)
            done_calls += 1
            row = score_case(case, outcome, latency, retries)
            rows.append(row)
            mark = "ok" if row["lenient_ok"] else ("ERR " + row["error"] if row["error"] else "miss")
            print(f"[{i}/{len(cases)}] {case['id']:<36} expected {row['expected']:<12} got {str(row['predicted']):<12} {mark}  {latency:.1f}s", flush=True)
            if row["error"] in RETRY_CODES:
                stopped = row["error"]
                print(f"stopping: {stopped} persists after {args.max_retries} retries")
            save(out_path, {**meta, "finished": None}, rows + [score_case(c, {"error": "not_run"}, 0.0, 0) for c in cases[len(rows):]])

    meta["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    m = save(out_path, meta, rows)
    print()
    print(report(m, meta))
    print(f"\nsaved {out_path}")
    left = sum(1 for r in rows if r["predicted"] is None)
    if left:
        print(f"{left} cases have no result; continue with: --resume --out {out_path}")
    if not todo:
        print("nothing to run: all selected cases were already completed")


if __name__ == "__main__":
    main()
