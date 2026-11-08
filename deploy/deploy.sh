#!/usr/bin/env bash
# Déploiement sur une VM Linux Ubuntu ou un serveur cloud (PARTIE 25)
#
#   curl -fsSL https://raw.githubusercontent.com/Joemagnan/ml-churn-project/main/deploy/deploy.sh -o deploy.sh
#   bash deploy.sh            # stack complète (≈ 4 Go de RAM conseillés)
#   bash deploy.sh --light    # sans ELK : api + interface + Prometheus + Grafana (≈ 1 Go)
#
# Le script installe Git et Docker si besoin, clone (ou met à jour) le dépôt,
# construit les images, lance la stack et vérifie /health et /predict.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Joemagnan/ml-churn-project.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-$HOME/ml-churn-project}"
SERVICES=""
[[ "${1:-}" == "--light" ]] && SERVICES="api frontend prometheus grafana"

echo "==> 1. Paquets système"
if ! command -v git > /dev/null || ! command -v docker > /dev/null; then
  sudo apt-get update
  sudo apt-get install -y git docker.io docker-compose-v2 curl
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="docker"
docker info > /dev/null 2>&1 || DOCKER="sudo docker"   # groupe docker actif après reconnexion

echo "==> 2. Code source (${BRANCH})"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
else
  git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
fi
cd "${APP_DIR}"
echo "Version déployée : $(git rev-parse --short HEAD)"

echo "==> 3. Elasticsearch : vm.max_map_count"
if [[ -z "${SERVICES}" ]]; then
  sudo sysctl -w vm.max_map_count=262144 > /dev/null
fi

echo "==> 4. Build et démarrage"
${DOCKER} compose build
# shellcheck disable=SC2086
${DOCKER} compose up -d ${SERVICES}
${DOCKER} compose ps

echo "==> 5. Vérification"
for i in $(seq 1 40); do
  if curl -sf http://localhost:8000/health > /dev/null; then break; fi
  sleep 3
done
curl -sf http://localhost:8000/health && echo
curl -sf -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":35,"anciennete":5,"revenu":450000,"nb_reclamations":2,"montant_mensuel":25000,"retards_paiement":2}'
echo

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
cat <<EOF

Déploiement terminé. Depuis votre poste (ports à ouvrir dans le pare-feu de la VM) :
  API         http://${IP}:8000/docs
  Interface   http://${IP}:8080
  Prometheus  http://${IP}:9090
  Grafana     http://${IP}:3000   (admin / admin, à changer via GRAFANA_ADMIN_PASSWORD)
  Kibana      http://${IP}:5601
Retour à une version précédente (tag Git) : BRANCH=v1.0.0 bash deploy.sh
EOF
