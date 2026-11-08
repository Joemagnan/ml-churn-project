# Image de l'API de prédiction du churn (PARTIE 14).
#
# Corrections par rapport au Dockerfile du sujet :
# - « COPY . . » copiait aussi .venv, .git, les tests et les données : seuls
#   l'API, le modèle et l'interface sont copiés (voir aussi .dockerignore) ;
# - Python 3.12 comme en local et en CI (le modèle est sérialisé avec ces versions) ;
# - l'API ne tourne pas en root ;
# - HEALTHCHECK : « docker ps » affiche (healthy) et docker-compose attend que
#   l'API soit prête avant de démarrer l'interface web ;
# - lancement par api/serve.py (voir docs/RAPPORT_INDUSTRIALISATION.md) :
#   * plusieurs workers uvicorn (WEB_CONCURRENCY) : un seul processus saturait un
#     cœur à ~30-40 req/s sous JMeter ;
#   * TCP_NODELAY : avec « uvicorn --workers », chaque réponse attendait ~40 ms
#     (algorithme de Nagle + accusé de réception retardé) ;
#   * pas de log d'accès uvicorn (le middleware écrit déjà un log JSON par requête),
#     en-têtes de proxy acceptés (IP réelle du client derrière Nginx) ;
# - Prometheus en mode multiprocessus, un fichier de logs par worker, un seul
#   thread BLAS par worker pour éviter la sursouscription CPU.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="ml-churn-api" \
      org.opencontainers.image.description="API FastAPI de prédiction du churn télécom" \
      org.opencontainers.image.authors="Joe MAGNAN" \
      org.opencontainers.image.version="1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_FILE=/app/logs/api.log \
    LOG_FILE_PER_PROCESS=1 \
    WEB_CONCURRENCY=4 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY models/model.pkl models/metadata.json ./models/
COPY frontend ./frontend

# logs/ appartient à appuser : un volume nommé monté dessus hérite de ces droits
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app/logs
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# Le dossier des métriques multiprocessus est vidé à chaque démarrage (sinon les
# compteurs d'anciens processus seraient additionnés aux nouveaux).
CMD ["sh", "-c", "rm -rf \"$PROMETHEUS_MULTIPROC_DIR\" && mkdir -p \"$PROMETHEUS_MULTIPROC_DIR\" && exec python -m api.serve"]
