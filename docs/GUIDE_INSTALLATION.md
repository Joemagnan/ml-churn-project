# Guide d'installation

Projet fil rouge MLOps – prédiction du churn télécom – Joe MAGNAN – MDSIA 2

Ce guide part d'une machine vierge et va jusqu'à la stack complète (API, interface,
Prometheus, Grafana, ELK). Les commandes sont données pour Ubuntu ; les équivalents
Windows sont indiqués lorsqu'ils diffèrent.

## 1. Prérequis

| Outil | Version testée | Vérification |
|---|---|---|
| Python | 3.12 | `python3 --version` |
| Git | 2.4x | `git --version` |
| Docker | 29.x | `docker --version` |
| Docker Compose | v2 / v5 | `docker compose version` |
| Google Chrome | récent | requis pour les tests Selenium |
| Java | 17 | requis pour JMeter (`java -version`) |
| Apache JMeter | 5.6.3 | tests de charge |

Installation sur Ubuntu (PARTIE 1 du sujet) :

```bash
sudo apt update
sudo apt install -y git python3-venv docker.io docker-compose-v2 tree
sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # puis se déconnecter / reconnecter
docker run hello-world
```

Mémoire : 4 Go libres pour la stack complète (Elasticsearch 1 Go, Logstash 512 Mo,
Kibana ~1 Go). Sans ELK, 1 Go suffit. Sous Linux, Elasticsearch demande aussi :

```bash
sudo sysctl -w vm.max_map_count=262144
```

## 2. Récupérer le projet

```bash
git clone https://github.com/Joemagnan/ml-churn-project.git
cd ml-churn-project
tree -L 2
```

## 3. Environnement Python

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements.txt` contient uniquement les dépendances de l'API (celles de l'image
Docker), `requirements-dev.txt` y ajoute la Data Science et les tests. Les versions
sont figées : le modèle `models/model.pkl` doit être rechargé avec la même version de
scikit-learn que celle qui l'a produit.

## 4. Data Science

```bash
python src/generate_data.py        # data/raw/churn.csv (2 000 clients, graine 42)
cd notebooks && python exploration.py && cd ..   # figures dans data/
python src/train.py                # compare 3 modèles, sauvegarde models/model.pkl
```

Le notebook exécuté est `notebooks/exploration.ipynb` (ouvrir avec Jupyter ou VS Code).

Options utiles de `train.py` :

| Commande | Effet |
|---|---|
| `python src/train.py --version 1.1.0` | produit la version 1.1.0 du modèle |
| `python src/train.py --model random_forest` | impose le Random Forest du sujet |
| `python src/train.py --min-f1 0.5` | échoue (code 1) si le F1 test est sous 0,5 |
| `python src/train.py --force` | promeut le modèle même s'il est moins bon |

## 5. API en local

```bash
uvicorn api.main:app --reload
```

- Documentation Swagger : http://127.0.0.1:8000/docs
- Interface web : http://127.0.0.1:8000/ui/
- Métriques : http://127.0.0.1:8000/metrics

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/model/info
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":35,"anciennete":5,"revenu":450000,"nb_reclamations":2,"montant_mensuel":25000,"retards_paiement":2}'
```

Sous PowerShell, utiliser `curl.exe` et un fichier pour le corps JSON, ou
`Invoke-RestMethod`.

## 6. Tests

```bash
pytest                               # tests unitaires, API, logs, modèle
pytest --cov=api --cov=src           # avec couverture
uvicorn api.main:app &               # puis, l'API étant lancée :
pytest -m e2e tests/test_selenium.py # tests Selenium (Chrome headless)
HEADLESS=0 pytest -m e2e tests/test_selenium.py   # pour voir le navigateur
```

## 7. Docker

API seule (PARTIE 14) :

```bash
docker build -t ml-churn-api:1.0 .
docker run -d --name ml-churn-api -p 8000:8000 ml-churn-api:1.0
docker ps                        # STATUS doit afficher (healthy)
curl http://localhost:8000/health
docker stop ml-churn-api && docker rm ml-churn-api
```

Stack complète (PARTIES 15 et 20 à 23) :

```bash
docker compose up -d --build
docker compose ps
docker compose logs api
docker compose down              # « down -v » supprime aussi les volumes (logs, métriques)
```

Sans ELK (petite machine) :

```bash
docker compose up -d --build api frontend prometheus grafana
```

| Service | URL | Identifiants |
|---|---|---|
| API (Swagger) | http://localhost:8000/docs | – |
| Interface web | http://localhost:8080 | – |
| Prometheus | http://localhost:9090 | – |
| Grafana | http://localhost:3000 | admin / admin (lecture anonyme activée) |
| Elasticsearch | http://localhost:9200 | – |
| Kibana | http://localhost:5601 | – |

Le dashboard Grafana « ML Churn API – Monitoring » et le dashboard Kibana
« ML Churn API – Logs » sont créés automatiquement.

**Port déjà utilisé ?** Copier `.env.example` en `.env` et changer `API_PORT`,
`FRONTEND_PORT`, etc., ou en ligne de commande : `API_PORT=8001 docker compose up -d`.

## 8. Tests de charge JMeter

```bash
# Linux
JMETER=/opt/apache-jmeter-5.6.3/bin/jmeter PORT=8000 ./jmeter/run_load_tests.sh
# Windows (PowerShell)
.\jmeter\run_load_tests.ps1 -JMeter "C:\outils\apache-jmeter-5.6.3\bin\jmeter.bat" -TargetHost 127.0.0.1 -Port 8000
```

Les rapports HTML sont dans `jmeter/results/<n>_users/report/index.html` et la
synthèse dans `jmeter/results/summary.md`. Sous Windows, cibler `127.0.0.1` plutôt
que `localhost` (sinon chaque connexion tente d'abord l'IPv6).

Pour ouvrir le plan en mode graphique : `jmeter -t jmeter/churn_test_plan.jmx`.

## 9. Déploiement sur une VM

```bash
curl -fsSL https://raw.githubusercontent.com/Joemagnan/ml-churn-project/main/deploy/deploy.sh -o deploy.sh
bash deploy.sh            # ou : bash deploy.sh --light (sans ELK)
curl http://SERVER_IP:8000/health
```

Ouvrir les ports 8000, 8080, 3000 (et 9090, 5601 si besoin) dans le pare-feu du
fournisseur cloud. Ne pas exposer Elasticsearch (9200) sur Internet : la sécurité
X-Pack y est désactivée pour le TP.

## 10. Problèmes connus

| Symptôme | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'api'` | pytest lancé sans `pytest.ini` | lancer depuis la racine du projet |
| `/health` renvoie 503 `DOWN` | `models/model.pkl` absent | `python src/train.py` |
| `port is already allocated` | un autre service utilise le port | changer le port dans `.env` |
| Elasticsearch redémarre en boucle | `vm.max_map_count` trop bas (Linux) | `sudo sysctl -w vm.max_map_count=262144` |
| Kibana vide | aucune requête encore envoyée à l'API | appeler `/predict`, attendre ~10 s |
| Montages de fichiers vides sous Docker Desktop | disque non partagé avec Docker | aucun : les configurations sont dans les images |
