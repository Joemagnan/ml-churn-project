"""Synthèse des campagnes JMeter (PARTIE 18).

Lit jmeter/results/<campagne>/<n>_users/results.jtl et calcule, pour chaque
série : moyenne, médiane, 90e / 95e / 99e percentiles, min, max, débit
(requêtes/s) et pourcentage d'erreurs. Écrit results/summary.md et summary.json.

    python jmeter/summarize_results.py
"""
import csv
import json
import math
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def percentile(sorted_values, p):
    """Percentile par la méthode du rang le plus proche (celle de JMeter)."""
    if not sorted_values:
        return 0
    rank = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def summarize(jtl: Path) -> dict:
    with jtl.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    elapsed = sorted(int(r["elapsed"]) for r in rows)
    errors = [r for r in rows if r["success"].lower() != "true"]
    start = min(int(r["timeStamp"]) for r in rows)
    end = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows)
    duration_s = max((end - start) / 1000, 1e-9)
    codes = {}
    for r in errors:
        codes[r["responseCode"]] = codes.get(r["responseCode"], 0) + 1
    return {
        "samples": len(rows),
        "users": max(int(r["allThreads"]) for r in rows),
        "average_ms": round(sum(elapsed) / len(elapsed), 1),
        "median_ms": percentile(elapsed, 50),
        "p90_ms": percentile(elapsed, 90),
        "p95_ms": percentile(elapsed, 95),
        "p99_ms": percentile(elapsed, 99),
        "min_ms": elapsed[0],
        "max_ms": elapsed[-1],
        "throughput_rps": round(len(rows) / duration_s, 1),
        "error_pct": round(100 * len(errors) / len(rows), 2),
        "error_codes": codes,
        "duration_s": round(duration_s, 1),
    }


def short_code(code: str) -> str:
    """« Non HTTP response code: java.net.SocketTimeoutException » -> « SocketTimeoutException »."""
    return code.rsplit(".", 1)[-1] if "Non HTTP" in code else code


def main() -> None:
    campaigns = {}
    for label_dir in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        runs = sorted(label_dir.glob("*_users/results.jtl"), key=lambda p: int(p.parent.name.split("_")[0]))
        if runs:
            campaigns[label_dir.name] = {jtl.parent.name: summarize(jtl) for jtl in runs}

    (RESULTS / "summary.json").write_text(json.dumps(campaigns, indent=2), encoding="utf-8")

    lines = ["# Résultats des tests de charge JMeter", "",
             "POST /predict, ramp-up 10 s, 10 boucles par utilisateur.", ""]
    for label, runs in campaigns.items():
        lines += [f"## {label.replace('_', ' ')}", "",
                  "| Utilisateurs | Requêtes | Moyenne (ms) | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) "
                  "| Max (ms) | Débit (req/s) | Erreurs (%) | Erreurs |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, s in runs.items():
            codes = ", ".join(f"{short_code(c)} × {n}" for c, n in s["error_codes"].items()) or "–"
            lines.append(
                f"| {name.split('_')[0]} | {s['samples']} | {s['average_ms']} | {s['median_ms']} "
                f"| {s['p90_ms']} | {s['p95_ms']} | {s['p99_ms']} | {s['max_ms']} | {s['throughput_rps']} "
                f"| {s['error_pct']} | {codes} |")
        lines.append("")
    (RESULTS / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
