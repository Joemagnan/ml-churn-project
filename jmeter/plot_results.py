"""Graphique avant / après optimisation à partir de jmeter/results/summary.json.

    python jmeter/summarize_results.py && python jmeter/plot_results.py
    -> docs/captures/jmeter_avant_apres.png
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "jmeter" / "results" / "summary.json"
OUT = ROOT / "docs" / "captures" / "jmeter_avant_apres.png"

SERIES = [("1_avant_optimisation", "Avant optimisation", "#C44E52"),
          ("2_apres_optimisation", "Après optimisation", "#4C72B0")]
USERS = ["100_users", "500_users", "1000_users"]


def main() -> None:
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    width = 0.38
    x = range(len(USERS))
    panels = [
        ("throughput_rps", "Débit (requêtes / s)", False, "{:.0f}"),
        ("p95_ms", "95e percentile du temps de réponse (ms, échelle log)", True, "{:.0f}"),
        ("error_pct", "Erreurs (%)", False, "{:.1f}"),
    ]
    for ax, (key, title, log, fmt) in zip(axes, panels):
        for i, (label, name, color) in enumerate(SERIES):
            values = [data[label][u][key] for u in USERS]
            positions = [p + (i - 0.5) * width for p in x]
            bars = ax.bar(positions, values, width, label=name, color=color)
            for bar, value in zip(bars, values):
                ax.annotate(fmt.format(value), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            ha="center", va="bottom", fontsize=9, xytext=(0, 2), textcoords="offset points")
        ax.set_title(title, fontsize=11)
        ax.set_xticks(list(x), [u.split("_")[0] + " utilisateurs" for u in USERS])
        if log:
            ax.set_yscale("log")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("Tests de charge JMeter – POST /predict (ramp-up 10 s, 10 boucles)", fontsize=13)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130)
    print("Graphique écrit :", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
