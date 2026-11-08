"""Tests du script d'entraînement et du modèle en production (PARTIE 6)."""
import json

import joblib
import pandas as pd
import pytest
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

import src.train as train
from src.generate_data import generate


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirige les sorties de train.py vers un dossier temporaire."""
    data = tmp_path / "churn.csv"
    generate().to_csv(data, index=False)
    monkeypatch.setattr(train, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(train, "REGISTRY_DIR", tmp_path / "models" / "registry")
    monkeypatch.setattr(train, "REPORTS_DIR", tmp_path / "reports")
    (tmp_path / "models").mkdir()
    return tmp_path, data


@pytest.mark.integration
def test_training_produces_versioned_artifacts(isolated_dirs):
    tmp, data = isolated_dirs
    assert train.main(["--data", str(data), "--version", "9.9.9"]) == 0

    meta = json.loads((tmp / "models" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["version"] == "9.9.9"
    assert meta["features"] == train.FEATURES
    assert (tmp / "models" / "registry" / "v9.9.9" / "model.pkl").exists()

    report = json.loads((tmp / "reports" / "metrics.json").read_text(encoding="utf-8"))
    assert set(report["results"]) == {"logistic_regression", "decision_tree", "random_forest"}

    model = joblib.load(tmp / "models" / "model.pkl")
    proba = model.predict_proba(generate().head(5)[train.FEATURES])
    assert proba.shape == (5, 2)


@pytest.mark.integration
def test_quality_gate_blocks_weak_model(isolated_dirs):
    tmp, data = isolated_dirs
    assert train.main(["--data", str(data), "--min-f1", "0.99"]) == 1
    assert not (tmp / "models" / "model.pkl").exists()


@pytest.mark.integration
def test_worse_model_is_not_promoted(isolated_dirs):
    tmp, data = isolated_dirs
    fake_prod = {"version": "1.0.0", "metrics_test": {"f1": 0.99}}
    (tmp / "models" / "metadata.json").write_text(json.dumps(fake_prod), encoding="utf-8")

    assert train.main(["--data", str(data), "--version", "2.0.0"]) == 0
    assert not (tmp / "models" / "model.pkl").exists()          # production inchangée
    assert (tmp / "models" / "registry" / "v2.0.0" / "model.pkl").exists()  # mais archivé


def test_load_data_rejects_missing_column(tmp_path):
    bad = tmp_path / "bad.csv"
    generate().drop(columns=["revenu"]).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="revenu"):
        train.load_data(bad)


def test_load_data_rejects_non_binary_target(tmp_path):
    df = generate()
    df.loc[0, "churn"] = 2
    bad = tmp_path / "bad.csv"
    df.to_csv(bad, index=False)
    with pytest.raises(ValueError, match="binaire"):
        train.load_data(bad)


def test_production_model_meets_minimum_quality():
    """Le modèle versionné dans models/ atteint le seuil de qualité sur le jeu de test."""
    model = joblib.load(train.MODELS_DIR / "model.pkl")
    df = pd.read_csv(train.DATA_PATH)
    _, X_test, _, y_test = train_test_split(
        df[train.FEATURES], df[train.TARGET], test_size=0.2,
        random_state=train.SEED, stratify=df[train.TARGET])
    assert f1_score(y_test, model.predict(X_test)) >= 0.45
