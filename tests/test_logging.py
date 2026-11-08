"""Tests de la journalisation structurée (PARTIE 19)."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from api.logging_config import LOGGER_NAME, JsonFormatter
from api.main import app

client = TestClient(app)


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(JsonFormatter().format(record)))


@pytest.fixture
def captured_logs():
    handler = ListHandler()
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    yield handler.lines
    logger.removeHandler(handler)


def test_formatter_produces_json_with_extra_fields():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "bonjour", (), None)
    record.model_version = "1.0.0"
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "bonjour"
    assert line["level"] == "INFO"
    assert line["model_version"] == "1.0.0"
    assert "timestamp" in line


def test_prediction_log_answers_who_what_when(payload, captured_logs):
    client.post("/predict", json=payload, headers={"X-Client-ID": "agence-dakar"})
    predict_log = next(line for line in captured_logs if line.get("operation") == "predict")
    for key in ["timestamp", "client_id", "request_id", "model_name", "model_version",
                "prediction", "probability", "response_time_ms"]:
        assert key in predict_log, key
    assert predict_log["client_id"] == "agence-dakar"


def test_one_log_line_per_prediction(payload, captured_logs):
    client.post("/predict", json=payload)
    lines = [line for line in captured_logs if line.get("endpoint") == "/predict"]
    assert len(lines) == 1
    assert lines[0]["operation"] == "predict"
    assert lines[0]["status_code"] == 200
    assert lines[0]["message"].startswith("Prediction request: model_version=")


def test_per_process_log_file_name():
    import os

    from api.logging_config import resolve_log_file

    assert resolve_log_file("/app/logs/api.log", per_process=False) == "/app/logs/api.log"
    per_process = resolve_log_file("/app/logs/api.log", per_process=True)
    assert per_process.replace("\\", "/").endswith(f"/app/logs/api-{os.getpid()}.log")
    assert resolve_log_file("", per_process=True) is None


def test_logs_do_not_contain_personal_data(payload, captured_logs):
    payload["revenu"] = 987654
    client.post("/predict", json=payload)
    assert "987654" not in json.dumps(captured_logs)


def test_model_error_is_logged_as_error(payload, captured_logs, monkeypatch):
    import api.main as api_main

    class BrokenModel:
        def predict_proba(self, _):
            raise RuntimeError("modèle corrompu")

    monkeypatch.setattr(api_main, "model", BrokenModel())
    client.post("/predict", json=payload)
    errors = [line for line in captured_logs if line["level"] == "ERROR"]
    assert errors and errors[0]["error"] == "modèle corrompu"
