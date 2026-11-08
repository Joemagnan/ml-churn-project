# Prometheus avec sa configuration intégrée (pas de montage de fichiers : même
# comportement sous Docker Desktop Windows, en CI et sur une VM Linux).
FROM prom/prometheus:v3.5.0
COPY prometheus.yml alerts.yml /etc/prometheus/
