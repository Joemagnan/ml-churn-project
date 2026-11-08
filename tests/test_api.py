"""Tests de l'API (PARTIE 11).

Les quatre premiers tests sont ceux du sujet, sans modification ; les suivants
vérifient le format des réponses, la validation des entrées, la gestion d'un
modèle absent et l'exposition des métriques.
"""
import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app

client = TestClient(app)


# --- Tests du sujet ---------------------------------------------------------------
def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_model_info():
    response = client.get("/model/info")
    assert response.status_code == 200


def test_prediction():
    payload = {
        "age": 35,
        "anciennete": 5,
        "revenu": 450000,
        "nb_reclamations": 2,
        "montant_mensuel": 25000,
        "retards_paiement": 2
    }
    response = client.post(
        "/predict",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "prediction" in data
    assert "probability" in data
    assert "model_version" in data


# --- Tests complémentaires --------------------------------------------------------
def test_prediction_response_format(payload):
    data = client.post("/predict", json=payload).json()
    assert data["prediction"] in {"CHURN", "NO_CHURN"}
    assert 0.0 <= data["probability"] <= 1.0
    assert data["model_version"] == api_main.metadata["version"]
    assert data["duration_ms"] >= 0


def test_prediction_is_deterministic(payload):
    first = client.post("/predict", json=payload).json()
    second = client.post("/predict", json=payload).json()
    assert first["probability"] == second["probability"]


def test_model_info_content():
    info = client.get("/model/info").json()
    assert info["model"] in {"Logistic Regression", "Decision Tree", "Random Forest"}
    assert info["features"] == api_main.FEATURES
    assert "f1" in info["metrics_test"]


@pytest.mark.parametrize("field", ["age", "anciennete", "revenu", "nb_reclamations",
                                   "montant_mensuel", "retards_paiement"])
def test_prediction_missing_field_returns_422(payload, field):
    payload.pop(field)
    assert client.post("/predict", json=payload).status_code == 422


@pytest.mark.parametrize("field,value", [("age", 10), ("anciennete", -1), ("revenu", -5),
                                         ("nb_reclamations", -2), ("age", "trente")])
def test_prediction_invalid_value_returns_422(payload, field, value):
    payload[field] = value
    assert client.post("/predict", json=payload).status_code == 422


def test_prediction_without_model_returns_503(payload, monkeypatch):
    monkeypatch.setattr(api_main, "model", None)
    assert client.post("/predict", json=payload).status_code == 503
    health = client.get("/health")
    assert health.status_code == 503
    assert health.json()["status"] == "DOWN"


def test_model_error_returns_500(payload, monkeypatch):
    class BrokenModel:
        def predict_proba(self, _):
            raise RuntimeError("modèle corrompu")

    monkeypatch.setattr(api_main, "model", BrokenModel())
    assert client.post("/predict", json=payload).status_code == 500


def test_request_id_is_returned(payload):
    response = client.post("/predict", json=payload, headers={"X-Request-ID": "test-123"})
    assert response.headers["X-Request-ID"] == "test-123"


def test_metrics_endpoint(payload):
    client.post("/predict", json=payload)
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "churn_predictions_total" in body
    assert "churn_prediction_duration_seconds" in body


def test_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "Churn Prediction API"


def test_web_interface_served():
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "predict-btn" in response.text
