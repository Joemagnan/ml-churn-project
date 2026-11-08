#!/bin/bash
# Configuration automatique de Kibana (lancé par le service kibana-setup) :
# vue de données ml-churn-logs-*, recherches « Prédictions » / « Erreurs »,
# visualisations et dashboard « ML Churn API – Logs ».
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"

echo "Attente de Kibana sur ${KIBANA_URL}..."
until curl -s "${KIBANA_URL}/api/status" | grep -q '"level":"available"'; do
  sleep 5
done

echo "Import des objets Kibana..."
result=$(curl -s -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  --form file=@/setup/ml-churn-kibana.ndjson)
echo "${result}"
echo "${result}" | grep -q '"success":true' || { echo "Échec de l'import"; exit 1; }

echo "Vue de données par défaut : ml-churn-logs"
curl -s -X POST "${KIBANA_URL}/api/kibana/settings" \
  -H "kbn-xsrf: true" -H "Content-Type: application/json" \
  -d '{"changes":{"defaultIndex":"ml-churn-logs"}}' > /dev/null

echo "Kibana prêt : ${KIBANA_URL}/app/dashboards#/view/dashboard-ml-churn"
