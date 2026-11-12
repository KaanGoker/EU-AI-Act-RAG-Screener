"""Retrieval test set and metrics: recall@5, recall@8 and MRR for BM25, dense and hybrid search.

Run from the repo root:  python eval/retrieval_eval.py [--kinds article,annex] [--misses]

Each query lists the units or parts that must come back. An expected unit id ("art-5") is found
by any hit from that unit; an expected part id ("annex-III-4") only by that part.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

# The repo root, so that "python eval/retrieval_eval.py" finds the app package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# (query, expected refs, language)
QUERIES: list[tuple[str, list[str], str]] = [
    # English: system descriptions
    ("CV screening tool that ranks job applicants and filters applications for recruiters", ["annex-III-4", "art-6"], "en"),
    ("Software that recognises the emotions of employees from their facial expressions at the workplace", ["art-5"], "en"),
    ("A customer service chatbot on our website that answers questions from consumers", ["art-50"], "en"),
    ("Credit scoring model that decides whether a consumer gets a loan", ["annex-III-5"], "en"),
    ("Social scoring of citizens by a public authority based on their social behaviour", ["art-5"], "en"),
    ("Real-time facial recognition of people in public spaces by the police", ["art-5"], "en"),
    ("An app that generates deepfake videos of real people", ["art-50", "art-3-60"], "en"),
    ("AI system that grades student exams and evaluates learning outcomes", ["annex-III-3"], "en"),
    ("Proctoring software that detects cheating by students during online tests", ["annex-III-3"], "en"),
    ("Large language model offered to other companies through an API, trained with more than 10^25 FLOPs", ["art-51", "art-55"], "en"),
    ("AI software used as a safety component in a medical device", ["art-6-1", "annex-I"], "en"),
    ("AI that triages emergency calls and dispatches ambulances", ["annex-III-5"], "en"),
    ("Predictive policing system that predicts whether a person will commit a crime based on profiling", ["art-5", "annex-III-6"], "en"),
    ("Scraping facial images from the internet and CCTV to build a face recognition database", ["art-5"], "en"),
    ("A system that manipulates users with subliminal techniques to change their behaviour", ["art-5"], "en"),
    ("Biometric categorisation of people to infer their race or sexual orientation", ["art-5"], "en"),
    ("AI that assists judges in researching and interpreting the law", ["annex-III-8"], "en"),
    ("Microtargeting political ads to influence how people vote in an election", ["annex-III-8"], "en"),
    ("Assessment of visa and asylum applications by migration authorities", ["annex-III-7"], "en"),
    ("AI controlling the electricity grid and water supply as a safety component", ["annex-III-2"], "en"),
    ("Pricing of life and health insurance based on personal data", ["annex-III-5"], "en"),
    ("Monitoring workers' performance and allocating tasks based on their behaviour", ["annex-III-4"], "en"),
    ("AI that decides who is eligible for public assistance benefits", ["annex-III-5"], "en"),
    ("AI-generated news articles published to inform the public on matters of public interest", ["art-50-4"], "en"),
    ("Voice assistant that synthesises audio content and images", ["art-50-2"], "en"),
    # English: questions
    ("What is the definition of an AI system?", ["art-3-1"], "en"),
    ("Who counts as a deployer?", ["art-3-4"], "en"),
    ("When does the regulation enter into force and from which date does it apply?", ["art-113"], "en"),
    ("Obligations for providers of general-purpose AI models: technical documentation and copyright policy", ["art-53"], "en"),
    ("Which penalties and fines apply for non-compliance?", ["art-99"], "en"),
    ("Human oversight requirements for high-risk AI systems", ["art-14"], "en"),
    ("Risk management system for high-risk AI", ["art-9"], "en"),
    ("Training data quality, data governance and bias", ["art-10"], "en"),
    ("Fundamental rights impact assessment by deployers", ["art-27"], "en"),
    ("AI literacy of staff", ["art-4"], "en"),
    ("An AI system that only performs a narrow procedural task is not high-risk", ["art-6-3"], "en"),
    ("Does the Act apply to AI used exclusively for military or defence purposes?", ["art-2-3"], "en"),
    ("Are AI systems released under free and open-source licences exempt?", ["art-2-12"], "en"),
    ("AI developed only for scientific research and development", ["art-2-6"], "en"),
    ("Obligations of providers of general-purpose AI models with systemic risk: adversarial testing and serious incidents", ["art-55"], "en"),
    ("AI regulatory sandboxes for start-ups", ["art-57"], "en"),
    ("Registration of high-risk AI systems in the EU database", ["art-49", "art-71"], "en"),
    ("Reporting serious incidents to market surveillance authorities", ["art-73"], "en"),
    ("Obligations of deployers of high-risk AI systems", ["art-26"], "en"),
    # English: provisions added or changed by Regulation (EU) 2026/1744
    ("Nudify app that generates sexually explicit images of a real person without their consent", ["art-5-1"], "en"),
    ("Can providers process special categories of personal data to detect and correct bias?", ["art-4a"], "en"),
    ("An AI feature in a machine that only optimises performance and user convenience: is it a safety component?", ["art-6-1a"], "en"),
    ("From which date do the high-risk rules for Annex III systems apply?", ["art-113"], "en"),
    ("Supervisory and enforcement powers of the AI Office over AI systems based on general-purpose AI models", ["art-75a"], "en"),
    ("Real-world testing of high-risk AI covered by Section B of Annex I outside a sandbox", ["art-60a"], "en"),
    ("Codes and categories of AI systems for the designation of notified bodies", ["annex-XIV"], "en"),
    # Dutch
    ("Een tool die cv's van sollicitanten automatisch screent en rangschikt", ["annex-III-4", "art-6"], "nl"),
    ("Chatbot voor klantenservice op onze website", ["art-50"], "nl"),
    ("Emotieherkenning van werknemers via camera's op de werkvloer", ["art-5"], "nl"),
    ("Beoordeling van de kredietwaardigheid van consumenten met AI", ["annex-III-5"], "nl"),
    ("App die zonder toestemming naaktbeelden van echte personen genereert", ["art-5-1"], "nl"),
    # French
    ("Système de reconnaissance faciale en temps réel dans l'espace public par la police", ["art-5"], "fr"),
    ("Outil qui génère des hypertrucages (deepfakes) de personnes réelles", ["art-50"], "fr"),
    ("Notation sociale des citoyens par l'administration publique", ["art-5"], "fr"),
    ("Logiciel qui corrige les examens des étudiants et évalue les acquis d'apprentissage", ["annex-III-3"], "fr"),
    # German
    ("KI-System zur Bewertung der Kreditwürdigkeit von Verbrauchern", ["annex-III-5"], "de"),
    ("Sprachmodell mit allgemeinem Verwendungszweck mit systemischem Risiko", ["art-51", "art-55"], "de"),
    ("Bewerbermanagement-Software, die Lebensläufe filtert und Bewerber bewertet", ["annex-III-4"], "de"),
    ("Welche Geldbußen drohen bei Verstößen gegen die Verordnung?", ["art-99"], "de"),
    # Turkish
    ("İş başvurularını otomatik olarak eleyen ve adayları sıralayan yapay zeka aracı", ["annex-III-4"], "tr"),
    ("Müşteri hizmetleri için sohbet robotu", ["art-50"], "tr"),
    ("Çalışanların yüz ifadelerinden duygularını tanıyan sistem", ["art-5"], "tr"),
    ("Polisin kamusal alanlarda gerçek zamanlı yüz tanıma kullanması", ["art-5"], "tr"),
    ("Tıbbi cihazlarda güvenlik bileşeni olarak kullanılan yapay zeka", ["art-6-1", "annex-I"], "tr"),
]


def is_hit(expected: str, ref: str, unit_id: str) -> bool:
    """A unit id is found by any hit from that unit; a part id only by itself."""
    if expected == ref:
        return True
    return expected == unit_id


def score(queries, results, k_values=(5, 8)) -> dict:
    """results[i] is the ranked (ref, unit_id) list for queries[i]."""
    out: dict = {}
    for k in k_values:
        recalls = []
        for (_, expected, _), hits in zip(queries, results):
            top = hits[:k]
            found = sum(1 for e in expected if any(is_hit(e, r, u) for r, u in top))
            recalls.append(found / len(expected))
        out[f"recall@{k}"] = statistics.mean(recalls)
    rr = []
    for (_, expected, _), hits in zip(queries, results):
        rank = next((i + 1 for i, (r, u) in enumerate(hits) if any(is_hit(e, r, u) for e in expected)), None)
        rr.append(1.0 / rank if rank else 0.0)
    out["mrr"] = statistics.mean(rr)
    return out


def by_language(queries, results) -> dict[str, dict]:
    groups: dict[str, list[int]] = {}
    for i, (_, _, lang) in enumerate(queries):
        groups.setdefault("en" if lang == "en" else "non-en", []).append(i)
    return {name: score([queries[i] for i in idx], [results[i] for i in idx]) for name, idx in groups.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="", help="comma list, for example article,annex (default: all kinds)")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--misses", action="store_true", help="print the queries hybrid search misses at 8")
    args = ap.parse_args()
    kinds = tuple(x for x in args.kinds.split(",") if x) or None

    from app.retrieval import EMBED_MODEL, get_retriever

    t0 = time.perf_counter()
    r = get_retriever()
    print(f"model {EMBED_MODEL}, ready {r.ready()}, {len(r.chunks)} chunks, load {time.perf_counter() - t0:.1f}s")
    if not r.ready():
        print("dense index not ready:", r.error)
        return 1
    r.search("warm up")

    modes = {"bm25": r.keyword_search, "dense": r.dense_search, "hybrid": r.search}
    print(f"{len(QUERIES)} queries, kinds {kinds or 'all'}")
    print(f"{'mode':8} {'recall@5':>9} {'recall@8':>9} {'mrr':>6}   en r@8 / non-en r@8   avg ms")
    hybrid_results = None
    for name, fn in modes.items():
        results, times = [], []
        for q, _, _ in QUERIES:
            t = time.perf_counter()
            hits = fn(q, k=args.k, kinds=kinds)
            times.append((time.perf_counter() - t) * 1000)
            results.append([(h.ref, h.unit_id) for h in hits])
        s = score(QUERIES, results)
        lang = by_language(QUERIES, results)
        print(
            f"{name:8} {s['recall@5']:9.3f} {s['recall@8']:9.3f} {s['mrr']:6.3f}   "
            f"{lang['en']['recall@8']:.3f} / {lang['non-en']['recall@8']:.3f}        {statistics.mean(times):6.1f}"
        )
        if name == "hybrid":
            hybrid_results = results
    if args.misses and hybrid_results:
        for (q, expected, _), hits in zip(QUERIES, hybrid_results):
            top = hits[:8]
            missing = [e for e in expected if not any(is_hit(e, rr, u) for rr, u in top)]
            if missing:
                print(f"MISS {missing} <- {q[:70]!r}: {[h[0] for h in top]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
