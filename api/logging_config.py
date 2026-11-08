"""Journalisation structurée de l'API (PARTIE 19).

Le sujet propose logging.basicConfig avec un format texte. Pour que Logstash et
Kibana puissent filtrer sur prediction, model_version, response_time_ms ou
level=ERROR sans expression régulière, chaque ligne est un objet JSON.

Chaque événement répond aux questions du sujet :
    Quand ?             timestamp (UTC, ISO 8601)
    Qui ?               client_id (en-tête X-Client-ID), client_ip, request_id
    Quelle opération ?  operation, method, endpoint
    Quel modèle ?       model_name, model_version
    Quel résultat ?     prediction, probability, status_code
    Combien de temps ?  response_time_ms
    Quelle erreur ?     level=ERROR, error, error_detail (trace)

Les données personnelles du client (âge, revenu…) ne sont pas journalisées.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "ml_churn"
SERVICE_NAME = "ml-churn-api"

_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["error_detail"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def resolve_log_file(log_file: str | None, per_process: bool) -> str | None:
    """Avec plusieurs workers uvicorn, chaque processus écrit dans son propre fichier
    (api-<pid>.log) : deux processus qui font tourner le même fichier se marchent
    dessus. Logstash lit tous les fichiers api*.log*."""
    if not log_file or not per_process:
        return log_file or None
    path = Path(log_file)
    return str(path.with_name(f"{path.stem}-{os.getpid()}{path.suffix}"))


def setup_logging(log_file: str | None) -> logging.Logger:
    """Logs JSON sur la sortie standard et, si log_file est défini, dans un fichier
    lu par Logstash (volume partagé dans docker-compose)."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:  # évite les doublons (rechargement uvicorn --reload, tests)
        return logger
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    formatter = JsonFormatter()

    if os.getenv("LOG_TO_STDOUT", "1") == "1":
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    log_file = resolve_log_file(log_file, os.getenv("LOG_FILE_PER_PROCESS", "0") == "1")
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=3,
                                          encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except OSError as exc:  # l'API doit démarrer même sans fichier de logs
            logger.warning("Fichier de logs inaccessible, logs sur la sortie standard seulement",
                           extra={"operation": "logging_setup", "error": str(exc)})
    return logger
