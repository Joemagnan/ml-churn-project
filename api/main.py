"""API FastAPI de prédiction du churn (PARTIES 7, 19 et 21).

Corrections par rapport au code du sujet :
- le modèle reçoit un DataFrame avec les noms de colonnes de l'entraînement
  (une liste de listes déclenche un avertissement scikit-learn et dépend de
  l'ordre des champs) ;
- predict_proba n'est appelé qu'une fois : la classe est déduite du seuil
  enregistré dans les métadonnées (le sujet calculait deux fois le modèle) ;
- la version et le nom du modèle viennent de models/metadata.json au lieu
  d'être écrits en dur à trois endroits ;
- les entrées sont validées (valeurs négatives ou âge irréaliste => 422) ;
- print() est remplacé par des logs JSON (logging_config.py) et les erreurs
  sont journalisées en ERROR puis renvoyées en 500 ;
- si le modèle est absent, l'API démarre quand même : /health répond DOWN (503)
  et /predict renvoie 503 au lieu de faire planter le démarrage ;
- métriques métier ajoutées à /metrics : nombre de prédictions par classe,
  erreurs, latence du modèle et distribution des probabilités.
"""
import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from pydantic import BaseModel, ConfigDict, Field

from api.logging_config import setup_logging

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "models" / "model.pkl"))
METADATA_PATH = Path(os.getenv("METADATA_PATH", MODEL_PATH.with_name("metadata.json")))
LOG_FILE = os.getenv("LOG_FILE", str(ROOT / "logs" / "api.log"))  # LOG_FILE="" : pas de fichier
FRONTEND_DIR = ROOT / "frontend"
API_VERSION = "1.0.0"
FEATURES = ["age", "anciennete", "revenu", "nb_reclamations", "montant_mensuel",
            "retards_paiement"]

logger = setup_logging(LOG_FILE)


def load_artifacts():
    """Charge le modèle et ses métadonnées. Ne charger que des fichiers .pkl de
    confiance : joblib/pickle peut exécuter du code à la désérialisation."""
    try:
        loaded = joblib.load(MODEL_PATH)
    except FileNotFoundError:
        logger.error("Modèle introuvable", extra={"operation": "load_model",
                                                  "model_path": str(MODEL_PATH)})
        return None, {"model_name": "aucun", "version": "none", "threshold": 0.5}
    meta = {}
    if METADATA_PATH.exists():
        meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    meta.setdefault("model_name", type(loaded).__name__)
    meta.setdefault("version", "1.0.0")
    meta.setdefault("threshold", 0.5)
    logger.info("Modèle chargé", extra={"operation": "load_model",
                                        "model_name": meta["model_name"],
                                        "model_version": meta["version"]})
    return loaded, meta


model, metadata = load_artifacts()

# --- Métriques Prometheus métier (en plus de celles de l'Instrumentator) ---------
PREDICTIONS = Counter("churn_predictions_total", "Nombre de prédictions",
                      ["prediction", "model_version"])
PREDICTION_ERRORS = Counter("churn_prediction_errors_total", "Erreurs de prédiction",
                            ["model_version"])
PREDICTION_LATENCY = Histogram(
    "churn_prediction_duration_seconds", "Durée du calcul du modèle",
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
)
PREDICTION_PROBABILITY = Histogram(
    "churn_prediction_probability", "Distribution des probabilités de churn prédites",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
# multiprocess_mode : avec plusieurs workers (PROMETHEUS_MULTIPROC_DIR), on garde le max
MODEL_INFO = Gauge("churn_model_info", "Modèle servi par l'API", ["model_name", "model_version"],
                   multiprocess_mode="max")
MODEL_INFO.labels(metadata["model_name"], metadata["version"]).set(1 if model else 0)


class ClientData(BaseModel):
    age: int = Field(ge=18, le=100, description="Âge du client (années)")
    anciennete: int = Field(ge=0, le=600, description="Ancienneté (mois)")
    revenu: float = Field(ge=0, description="Revenu mensuel (FCFA)")
    nb_reclamations: int = Field(ge=0, le=100, description="Nombre de réclamations")
    montant_mensuel: float = Field(ge=0, description="Facture mensuelle (FCFA)")
    retards_paiement: int = Field(ge=0, le=100, description="Nombre de retards de paiement")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "age": 35, "anciennete": 5, "revenu": 450000, "nb_reclamations": 2,
        "montant_mensuel": 25000, "retards_paiement": 2,
    }]})


class PredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prediction: Literal["CHURN", "NO_CHURN"]
    probability: float
    model_version: str
    duration_ms: float


app = FastAPI(
    title="Churn Prediction API",
    version=API_VERSION,
    description="Prédiction du churn des clients d'un opérateur télécom.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Client-ID", "X-Request-ID"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Une seule ligne de log par requête HTTP : opération, statut, temps de réponse,
    appelant, et pour /predict le modèle et le résultat (renseignés par l'endpoint
    dans request.state.log_extra). Les tests de charge ont montré que deux lignes
    par prédiction coûtaient cher en débit."""
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.log_extra = None
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path != "/metrics":  # Prometheus interroge toutes les 5 s : bruit inutile
        extra = {
            "operation": "http_request",
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "response_time_ms": round((time.perf_counter() - start) * 1000, 2),
            "client_id": request.headers.get("X-Client-ID", "anonymous"),
            "client_ip": request.client.host if request.client else None,
            "request_id": request.state.request_id,
            "model_version": metadata["version"],
        }
        message = "HTTP request"
        if request.state.log_extra:  # prédiction réussie
            extra.update(request.state.log_extra)
            message = f"Prediction request: model_version={extra['model_version']}"
        logger.info(message, extra=extra)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.get("/")
def root():
    return {
        "application": "Churn Prediction API",
        "version": API_VERSION,
        "status": "running",
        "model_version": metadata["version"],
        "docs": "/docs",
        "ui": "/ui/",
    }


@app.get("/health")
def health():
    if model is None:
        return JSONResponse(status_code=503, content={"status": "DOWN", "model_loaded": False})
    return {"status": "UP", "model_loaded": True, "model_version": metadata["version"]}


@app.get("/model/info")
def model_info():
    return {
        "model": metadata["model_name"],
        "version": metadata["version"],
        "trained_at": metadata.get("trained_at"),
        "features": metadata.get("features", FEATURES),
        "threshold": metadata["threshold"],
        "selection_reason": metadata.get("selection_reason"),
        "metrics_test": metadata.get("metrics_test"),
        "sklearn_version": metadata.get("sklearn_version"),
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(data: ClientData, request: Request):
    version = metadata["version"]
    who = {
        "client_id": request.headers.get("X-Client-ID", "anonymous"),
        "request_id": getattr(request.state, "request_id", None),
    }
    if model is None:
        PREDICTION_ERRORS.labels(version).inc()
        logger.error("Prediction error", extra={"operation": "predict", "error": "model not loaded",
                                                "model_version": version, **who})
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    start = time.perf_counter()
    try:
        values = pd.DataFrame([data.model_dump()], columns=FEATURES)
        probability = float(model.predict_proba(values)[0][1])
    except Exception as exc:  # erreur du modèle : journalisée puis renvoyée en 500
        PREDICTION_ERRORS.labels(version).inc()
        logger.error("Prediction error", exc_info=True, extra={
            "operation": "predict", "error": str(exc), "model_version": version, **who})
        raise HTTPException(status_code=500, detail="Erreur lors de la prédiction") from exc
    duration = time.perf_counter() - start

    prediction = "CHURN" if probability >= metadata["threshold"] else "NO_CHURN"
    PREDICTIONS.labels(prediction, version).inc()
    PREDICTION_LATENCY.observe(duration)
    PREDICTION_PROBABILITY.observe(probability)

    # Champs ajoutés à la ligne de log de la requête (voir log_requests)
    request.state.log_extra = {
        "operation": "predict",
        "model_name": metadata["model_name"],
        "model_version": version,
        "prediction": prediction,
        "probability": round(probability, 4),
        "model_time_ms": round(duration * 1000, 2),
    }
    return {
        "prediction": prediction,
        "probability": round(probability, 4),
        "model_version": version,
        "duration_ms": round(duration * 1000, 2),
    }


# Interface web servie aussi par l'API (développement local et test Selenium en CI) ;
# dans docker-compose, elle est servie par Nginx sur le port 8080.
if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")

# /metrics : requêtes, latence, codes HTTP par endpoint (format Prometheus)
instrumentator = Instrumentator(excluded_handlers=["/metrics", "/ui"])
instrumentator.add(metrics.default(
    latency_lowr_buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
))
instrumentator.instrument(app).expose(app, include_in_schema=False)
