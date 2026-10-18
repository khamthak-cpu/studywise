"""Compare: no RAG vs offline RAG vs online hybrid.  Writes results.md + results.json.

    uvicorn app.main:app   (in another terminal, from backend/)
    python evaluation/run_eval.py
"""
import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from ollama import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings  # noqa: E402

HERE = Path(__file__).resolve().parent
LABELS = {"no_rag": "No RAG (LLM only)", "offline_rag": "Offline RAG", "online_hybrid": "Online hybrid"}
CITE_RE = re.compile(r"\[\d+\]")


def norm(s: str) -> str:
    return "".join(s.casefold().split())


def keyword_ratio(answer: str, kws: list[str]) -> float:
    a = norm(answer)
    return sum(norm(k) in a for k in kws) / len(kws) if kws else 0.0


def rate(xs: list) -> float | None:
    xs = [bool(x) for x in xs]
    return sum(xs) / len(xs) if xs else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


# ---------- runners ----------
def make_runners(cfg, api: str):
    ollama = Client(host=cfg.ollama_host, timeout=cfg.llm_timeout_s)
    http = httpx.Client(timeout=cfg.llm_timeout_s + 30)

    def no_rag(q: dict) -> dict:
        system = "You are a study tutor for Indian school students (Class 8-12). Answer concisely and accurately."
        if q.get("language") == "hi":
            system += " Answer in simple Hindi."
        res = ollama.chat(
            model=cfg.llm_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": q["question"]}],
            options={"temperature": cfg.temperature, "num_ctx": cfg.num_ctx, "num_predict": cfg.max_new_tokens},
            keep_alive=cfg.keep_alive,
        )
        return {"answer": res.message.content, "answered_from": "no_rag", "confidence": 0.0,
                "source_titles": [], "online": False}

    def via_api(mode: str):
        def run(q: dict) -> dict:
            r = http.post(f"{api}/ask", json={
                "question": q["question"], "class_level": q.get("class_level"), "subject": q.get("subject"),
                "language": q.get("language", "auto"), "mode": mode,
            })
            r.raise_for_status()
            d = r.json()
            return {"answer": d["answer"], "answered_from": d["answered_from"], "confidence": d["confidence"],
                    "source_titles": [s["title"] for s in d["sources"]], "online": d["online"]}
        return run

    return {"no_rag": no_rag, "offline_rag": via_api("offline"), "online_hybrid": via_api("auto")}, http


# ---------- scoring ----------
def evaluate(q: dict, run, system: str) -> dict:
    t0 = time.perf_counter()
    try:
        rec = run(q)
        rec["error"] = None
    except Exception as e:
        rec = {"answer": "", "answered_from": "error", "confidence": 0.0, "source_titles": [],
               "online": False, "error": str(e)[:200]}
    rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    rec.update(id=q["id"], question=q["question"], subject=q.get("subject"), answerable=q["answerable"])

    if q["answerable"]:
        ratio = keyword_ratio(rec["answer"], q.get("keywords", []))
        rec["correct"] = rec["answered_from"] not in ("fallback", "error") and ratio >= q.get("pass_ratio", 0.6)
        hint = q.get("chapter_hint")
        rec["retrieval_hit"] = (any(hint.casefold() in t.casefold() for t in rec["source_titles"])
                                if hint and system != "no_rag" else None)
    else:  # must not present a textbook-grounded answer to an out-of-syllabus question
        rec["correct"] = None if system == "no_rag" else rec["answered_from"] in ("fallback", "web")
        rec["retrieval_hit"] = None
    return rec


def summarize(recs: list[dict]) -> dict:
    ans = [r for r in recs if r["answerable"]]
    una = [r for r in recs if not r["answerable"] and r["correct"] is not None]
    lat = sorted(r["latency_ms"] for r in recs if not r["error"])
    grounded = [r for r in ans if r["answered_from"] in ("notes", "web")]
    return {
        "accuracy": rate([r["correct"] for r in ans]),
        "refusal": rate([r["correct"] for r in una]),
        "retrieval_hit": rate([r["retrieval_hit"] for r in ans if r["retrieval_hit"] is not None]),
        "citation": rate([CITE_RE.search(r["answer"]) for r in grounded]),
        "avg_s": statistics.mean(lat) / 1000 if lat else 0,
        "p50_s": lat[len(lat) // 2] / 1000 if lat else 0,
        "p95_s": lat[min(len(lat) - 1, int(0.95 * len(lat)))] / 1000 if lat else 0,
        "errors": sum(1 for r in recs if r["error"]),
    }


def sweep_threshold(recs: list[dict]) -> tuple[float, float, float, float] | None:
    """Best MIN_SCORE: maximises balanced accuracy of 'is the question answerable from the notes?'"""
    recs = [r for r in recs if not r["error"]]
    if not any(r["answerable"] for r in recs) or all(r["answerable"] for r in recs):
        return None
    scored = []
    for i in range(10, 91, 1):
        t = i / 100
        tp = sum(r["answerable"] and r["confidence"] >= t for r in recs)
        fn = sum(r["answerable"] and r["confidence"] < t for r in recs)
        tn = sum(not r["answerable"] and r["confidence"] < t for r in recs)
        fp = sum(not r["answerable"] and r["confidence"] >= t for r in recs)
        tpr, tnr = tp / (tp + fn), tn / (tn + fp)
        scored.append((t, (tpr + tnr) / 2, tpr, tnr))
    best = max(s[1] for s in scored)
    ties = [s for s in scored if s[1] == best]
    return ties[len(ties) // 2]  # middle of the plateau is the most stable choice


# ---------- report ----------
def write_report(path: Path, cfg, qs, results: dict, sums: dict, sweep) -> None:
    n_ans = sum(q["answerable"] for q in qs)
    L = [f"# Evaluation results\n",
         f"_Run: {datetime.now():%Y-%m-%d %H:%M} | LLM: `{cfg.llm_model}` | Embeddings: `{cfg.embed_model}` | "
         f"{len(qs)} questions ({n_ans} answerable, {len(qs) - n_ans} out-of-syllabus)_\n",
         "## Summary\n",
         "| System | Accuracy | Refusal OK | Retrieval hit | Cited | Avg time | p95 time | Errors |",
         "|---|---|---|---|---|---|---|---|"]
    for s, m in sums.items():
        L.append(f"| {LABELS[s]} | {pct(m['accuracy'])} | {pct(m['refusal'])} | {pct(m['retrieval_hit'])} | "
                 f"{pct(m['citation'])} | {m['avg_s']:.1f}s | {m['p95_s']:.1f}s | {m['errors']} |")

    subjects = sorted({q["subject"] for q in qs if q["answerable"] and q.get("subject")})
    L += ["\n## Accuracy by subject (answerable questions)\n",
          "| Subject | " + " | ".join(LABELS[s] for s in results) + " |",
          "|---|" + "---|" * len(results)]
    for sub in subjects:
        row = [pct(rate([r["correct"] for r in recs if r["answerable"] and r["subject"] == sub]))
               for recs in results.values()]
        L.append(f"| {sub} | " + " | ".join(row) + " |")

    if sweep:
        t, bal, tpr, tnr = sweep
        L += ["\n## Confidence threshold\n",
              f"Suggested `MIN_SCORE={t:.2f}` (balanced accuracy {bal * 100:.0f}%: answers {tpr * 100:.0f}% of "
              f"in-syllabus questions, refuses {tnr * 100:.0f}% of out-of-syllabus ones)."]

    L.append("\n## Failures to inspect\n")
    for s, recs in results.items():
        bad = [r for r in recs if r["correct"] is False]
        L.append(f"**{LABELS[s]}**: " + (", ".join(f"`{r['id']}`" for r in bad) or "none"))
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--systems", nargs="+", default=list(LABELS), choices=list(LABELS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()

    qs = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    if args.limit:
        qs = qs[:args.limit]
    cfg = get_settings()
    runners, http = make_runners(cfg, args.api)

    if any(s != "no_rag" for s in args.systems):
        try:
            h = http.get(f"{args.api}/health").json()
        except Exception as e:
            sys.exit(f"API not reachable at {args.api}: {e}")
        if h["status"] != "ok":
            print(f"WARNING: /health says {h}")
        if "online_hybrid" in args.systems and not h["online"]:
            print("WARNING: no internet; 'online hybrid' will behave like offline RAG.")

    results = {}
    for system in args.systems:
        print(f"\n== {LABELS[system]} ==")
        if not args.no_warmup:
            try:
                runners[system](qs[0])  # load models so timings are fair
            except Exception:
                pass
        recs = []
        for i, q in enumerate(qs, 1):
            rec = evaluate(q, runners[system], system)
            recs.append(rec)
            mark = {True: "PASS", False: "FAIL", None: "  - "}[rec["correct"]]
            print(f"[{i:>2}/{len(qs)}] {mark} {rec['id']:<5} {rec['answered_from']:<8} "
                  f"{rec['latency_ms'] / 1000:>5.1f}s {rec['error'] or ''}")
        results[system] = recs

    sums = {s: summarize(r) for s, r in results.items()}
    sweep = sweep_threshold(results["offline_rag"]) if "offline_rag" in results else None
    (HERE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(HERE / "results.md", cfg, qs, results, sums, sweep)
    print(f"\nWrote {HERE / 'results.md'}")


if __name__ == "__main__":
    main()