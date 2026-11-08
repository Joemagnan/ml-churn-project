"""Génération du dataset pédagogique de churn télécom (PARTIE 4).

Le code reprend celui du sujet (mêmes distributions, même graine 42) avec deux
corrections :
- le chemin de sortie ne dépend plus du dossier depuis lequel on lance le script ;
- le dossier data/raw est créé s'il n'existe pas.

Exécution (depuis la racine du projet) :
    python src/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "raw" / "churn.csv"

SEED = 42
N_CLIENTS = 2000


def generate(n: int = N_CLIENTS, seed: int = SEED) -> pd.DataFrame:
    np.random.seed(seed)

    age = np.random.randint(18, 70, n)
    anciennete = np.random.randint(1, 120, n)          # en mois
    revenu = np.random.randint(150000, 1000000, n)      # en FCFA
    nb_reclamations = np.random.poisson(2, n)
    montant_mensuel = np.random.randint(5000, 75000, n)  # en FCFA
    retards_paiement = np.random.poisson(1, n)

    # Score latent : plus de réclamations / retards / facture élevée => plus de churn,
    # plus d'ancienneté => moins de churn. L'âge et le revenu n'ont aucun effet.
    score = (
        0.04 * nb_reclamations
        + 0.08 * retards_paiement
        - 0.015 * anciennete
        + 0.00001 * montant_mensuel
    )
    probabilite = 1 / (1 + np.exp(-score))
    churn = (np.random.random(n) < probabilite).astype(int)

    return pd.DataFrame({
        "age": age,
        "anciennete": anciennete,
        "revenu": revenu,
        "nb_reclamations": nb_reclamations,
        "montant_mensuel": montant_mensuel,
        "retards_paiement": retards_paiement,
        "churn": churn,
    })


def main() -> None:
    df = generate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # lineterminator fixé : même fichier (et même empreinte SHA-256) sous Windows et Linux
    df.to_csv(OUTPUT, index=False, lineterminator="\n")
    print(df.head())
    print()
    print(df["churn"].value_counts())
    print(f"\nDataset écrit dans {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
