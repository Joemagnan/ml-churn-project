"""Exploration des données (PARTIE 5).

Corrections par rapport au sujet :
- les chemins sont calculés à partir de l'emplacement du script : il fonctionne
  lancé depuis notebooks/ (comme dans le sujet) ou depuis la racine ;
- plt.show() bloque l'exécution (et plante sans écran, en CI ou dans Docker) :
  les figures sont enregistrées, et affichées seulement avec l'option --show ;
- ajout de deux analyses utiles pour la soutenance : taux de churn par tranche
  d'ancienneté et distribution de chaque variable selon le churn.

Exécution :
    cd notebooks && python exploration.py && cd ..
    (ou depuis la racine : python notebooks/exploration.py)
"""
import sys
from pathlib import Path

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "churn.csv"
FIG_DIR = ROOT / "data"


def main() -> None:
    df = pd.read_csv(DATA)

    print(df.head())
    print("\nDimensions :")
    print(df.shape)
    print("\nTypes :")
    print(df.dtypes)
    print("\nValeurs manquantes :")
    print(df.isnull().sum())
    print("\nStatistiques :")
    print(df.describe())
    print("\nRépartition du churn :")
    print(df["churn"].value_counts())
    print(f"Taux de churn : {df['churn'].mean():.1%}")

    # 1. Répartition de la cible
    plt.figure(figsize=(6, 4))
    sns.countplot(data=df, x="churn")
    plt.title("Répartition des clients selon le churn")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "churn_distribution.png", dpi=120)

    # 2. Corrélations
    plt.figure(figsize=(10, 6))
    sns.heatmap(df.corr(), annot=True, fmt=".2f", cmap="coolwarm", center=0)
    plt.title("Corrélations")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "correlation.png", dpi=120)

    # 3. Taux de churn par tranche d'ancienneté
    tranches = pd.cut(df["anciennete"], bins=[0, 12, 24, 48, 72, 120],
                      labels=["0-12", "13-24", "25-48", "49-72", "73-120"])
    taux = df.groupby(tranches, observed=True)["churn"].mean()
    print("\nTaux de churn par ancienneté (mois) :")
    print(taux.round(3))
    plt.figure(figsize=(7, 4))
    taux.plot(kind="bar", color="#4C72B0")
    plt.ylabel("Taux de churn")
    plt.xlabel("Ancienneté (mois)")
    plt.title("Taux de churn par tranche d'ancienneté")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "churn_par_anciennete.png", dpi=120)

    # 4. Distribution de chaque variable selon le churn
    features = [c for c in df.columns if c != "churn"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    for ax, col in zip(axes.ravel(), features):
        sns.boxplot(data=df, x="churn", y=col, ax=ax)
        ax.set_title(col)
    fig.suptitle("Distribution des variables selon le churn")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "boxplots_variables.png", dpi=120)

    print(f"\nFigures enregistrées dans {FIG_DIR.relative_to(ROOT)}/")
    if "--show" in sys.argv:
        plt.show()


if __name__ == "__main__":
    main()
