"""Entraînement et comparaison des modèles de churn (PARTIE 6).

Le sujet compare Logistic Regression, Decision Tree et Random Forest puis garde
d'office le Random Forest. Corrections et ajouts :
- les trois modèles sont des Pipelines (le scaler n'est utile qu'à la régression
  logistique, mais tout est sauvegardé sous la même forme) ;
- le choix du modèle est justifié par une validation croisée stratifiée (5 plis)
  sur le jeu d'entraînement : le jeu de test ne sert qu'à l'évaluation finale ;
- ajout du ROC-AUC et de la matrice de confusion ;
- le modèle est versionné : models/registry/v<version>/ garde chaque version,
  models/model.pkl + models/metadata.json désignent la version en production ;
- garde-fou qualité : un modèle moins bon que celui en production n'est pas
  promu (sauf --force), et un F1 sous --min-f1 fait échouer le script (CI).

Exécution (depuis la racine) :
    python src/train.py
    python src/train.py --version 1.1.0
    python src/train.py --model random_forest   # imposer le choix du sujet
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "churn.csv"
MODELS_DIR = ROOT / "models"
REGISTRY_DIR = MODELS_DIR / "registry"
REPORTS_DIR = ROOT / "reports"

FEATURES = [
    "age",
    "anciennete",
    "revenu",
    "nb_reclamations",
    "montant_mensuel",
    "retards_paiement",
]
TARGET = "churn"
SEED = 42
THRESHOLD = 0.5

DISPLAY_NAMES = {
    "logistic_regression": "Logistic Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
}


def build_models() -> dict:
    return {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000)),
        ]),
        "decision_tree": Pipeline([
            ("model", DecisionTreeClassifier(max_depth=5, random_state=SEED)),
        ]),
        "random_forest": Pipeline([
            ("model", RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=1)),
        ]),
    }


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name} : {missing}")
    if df[FEATURES + [TARGET]].isnull().any().any():
        raise ValueError("Le dataset contient des valeurs manquantes")
    if not set(df[TARGET].unique()) <= {0, 1}:
        raise ValueError("La cible churn doit être binaire (0/1)")
    return df


def evaluate(model, X, y) -> dict:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= THRESHOLD).astype(int)
    return {
        "accuracy": round(accuracy_score(y, pred), 4),
        "precision": round(precision_score(y, pred, zero_division=0), 4),
        "recall": round(recall_score(y, pred, zero_division=0), 4),
        "f1": round(f1_score(y, pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y, proba), 4),
        "confusion_matrix": confusion_matrix(y, pred).tolist(),
    }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display(path: Path) -> str:
    """Chemin relatif au projet si possible, absolu sinon (format POSIX)."""
    path = Path(path).resolve()
    return (path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).as_posix()


def current_production_f1() -> float | None:
    meta_path = MODELS_DIR / "metadata.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta.get("metrics_test", {}).get("f1")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Entraînement des modèles de churn")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--version", default="1.0.0", help="version du modèle produit")
    parser.add_argument("--model", choices=list(DISPLAY_NAMES), default=None,
                        help="imposer un modèle au lieu de la sélection automatique")
    parser.add_argument("--selection-metric", choices=["f1", "roc_auc", "accuracy"], default="f1")
    parser.add_argument("--min-f1", type=float, default=0.45,
                        help="F1 minimal sur le jeu de test, sinon échec (code 1)")
    parser.add_argument("--tolerance", type=float, default=0.01,
                        help="perte de F1 tolérée par rapport au modèle en production")
    parser.add_argument("--force", action="store_true",
                        help="promouvoir même si le modèle est moins bon que la production")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    df = load_data(args.data)
    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )
    print(f"Train : {len(X_train)} clients | Test : {len(X_test)} clients | "
          f"taux de churn : {y.mean():.1%}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    results = {}
    fitted = {}
    for name, model in build_models().items():
        print(f"\nEntraînement : {name}")
        scores = cross_validate(model, X_train, y_train, cv=cv,
                                scoring=["f1", "roc_auc", "accuracy"])
        model.fit(X_train, y_train)
        fitted[name] = model
        results[name] = {
            "cv": {
                metric: round(float(scores[f"test_{metric}"].mean()), 4)
                for metric in ["f1", "roc_auc", "accuracy"]
            },
            "test": evaluate(model, X_test, y_test),
        }
        print(f"  CV (5 plis) : {results[name]['cv']}")
        print(f"  Test        : { {k: v for k, v in results[name]['test'].items() if k != 'confusion_matrix'} }")

    if args.model:
        chosen = args.model
        reason = f"modèle imposé par l'option --model {chosen}"
    else:
        chosen = max(results, key=lambda n: results[n]["cv"][args.selection_metric])
        reason = (f"meilleur {args.selection_metric} moyen en validation croisée 5 plis "
                  f"({results[chosen]['cv'][args.selection_metric]})")
    print(f"\nModèle retenu : {DISPLAY_NAMES[chosen]} — {reason}")

    test_metrics = results[chosen]["test"]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "metrics.json").write_text(json.dumps({
        "selected_model": chosen,
        "selection_reason": reason,
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    if test_metrics["f1"] < args.min_f1:
        print(f"ÉCHEC : F1 test {test_metrics['f1']} < seuil minimal {args.min_f1}")
        return 1

    metadata = {
        "model_name": DISPLAY_NAMES[chosen],
        "model_key": chosen,
        "version": args.version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": FEATURES,
        "target": TARGET,
        "threshold": THRESHOLD,
        "selection_reason": reason,
        "metrics_cv": results[chosen]["cv"],
        "metrics_test": test_metrics,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "data_file": display(args.data),
        "data_sha256": file_sha256(args.data),
        "sklearn_version": sklearn.__version__,
        "python_version": sys.version.split()[0],
    }

    # 1. Archivage systématique dans le registre local (permet le retour arrière)
    version_dir = REGISTRY_DIR / f"v{args.version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[chosen], version_dir / "model.pkl")
    (version_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Version archivée dans {display(version_dir)}")

    # 2. Promotion en production seulement si le modèle n'est pas moins bon
    prod_f1 = current_production_f1()
    if prod_f1 is not None and test_metrics["f1"] < prod_f1 - args.tolerance and not args.force:
        print(f"NON PROMU : F1 {test_metrics['f1']} < F1 en production {prod_f1} "
              f"(tolérance {args.tolerance}). Utiliser --force pour forcer.")
        return 0

    shutil.copy2(version_dir / "model.pkl", MODELS_DIR / "model.pkl")
    shutil.copy2(version_dir / "metadata.json", MODELS_DIR / "metadata.json")
    print("\nModèle sauvegardé dans models/model.pkl (version "
          f"{args.version}, métadonnées dans models/metadata.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
