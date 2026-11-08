# ML Churn Project – Prédiction du churn d'un opérateur télécom

**Projet fil rouge MLOps – Industrialisation du développement ML – Joe MAGNAN – MDSIA 2**

[![CI ML Churn](https://github.com/Joemagnan/ml-churn-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Joemagnan/ml-churn-project/actions/workflows/ci.yml)

> J'ai développé un modèle de Machine Learning, je l'ai exposé sous forme d'API,
> testé automatiquement, versionné avec Git, conteneurisé avec Docker, intégré dans
> une chaîne CI/CD, préparé pour le déploiement, soumis à des tests de charge et placé
> sous observabilité grâce aux logs, aux métriques et aux dashboards.

## Architecture

```
 Utilisateur ─► Interface web (Nginx :8080) ─► FastAPI (:8000) ─► modèle (Logistic Regression v1.0.0)
                                                   │
                     logs JSON ─► Logstash ─► Elasticsearch (:9200) ─► Kibana (:5601)
                     /metrics  ─► Prometheus (:9090) ─► Grafana (:3000)

 Développeur ─► Git (feature → develop → main) ─► GitHub Actions
                 ├── tests unitaires, API, intégration (pytest)
                 ├── tests E2E (Selenium)
                 ├── build Docker + test de la stack
                 └── publication de l'image (GHCR)
```

## Démarrage rapide

```bash
git clone https://github.com/Joemagnan/ml-churn-project.git && cd ml-churn-project
docker compose up -d --build
```

| Service | URL |
|---|---|
| Interface web | http://localhost:8080 |
| API – Swagger | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (dashboard « ML Churn API – Monitoring ») |
| Kibana | http://localhost:5601 (dashboard « ML Churn API – Logs ») |
| Prometheus | http://localhost:9090 |

Installation complète, environnement Python et dépannage : [docs/GUIDE_INSTALLATION.md](docs/GUIDE_INSTALLATION.md).

## Vérification finale (PARTIE 26)

```bash
# 1. Data Science
python src/generate_data.py
python src/train.py
# 2. API
uvicorn api.main:app --reload
# 3. Tests
pytest
pytest -m e2e tests/test_selenium.py        # API lancée
# 4. Docker
docker build -t ml-churn-api:1.0 .
docker run -p 8000:8000 ml-churn-api:1.0
# 5. CI/CD : git push → GitHub Actions → tests → build
# 6. Performance (100 / 500 / 1000 utilisateurs)
./jmeter/run_load_tests.sh                   # Windows : .\jmeter\run_load_tests.ps1
# 7. Logs : FastAPI → Logstash → Elasticsearch → Kibana
# 8. Monitoring : FastAPI → Prometheus → Grafana
docker compose up -d --build
```

## Livrables (PARTIE 27)

| # | Livrable | Emplacement |
|---|---|---|
| 1 | Repository Git | ce dépôt (branches `main`, `develop`, `feature/*`) |
| 2 | Dataset | [data/raw/churn.csv](data/raw/churn.csv) – généré par [src/generate_data.py](src/generate_data.py) |
| 3 | Notebook Data Science | [notebooks/exploration.ipynb](notebooks/exploration.ipynb) (exécuté) et [notebooks/exploration.py](notebooks/exploration.py) |
| 4 | Script d'entraînement | [src/train.py](src/train.py) |
| 5 | Modèle ML | [models/model.pkl](models/model.pkl) + [models/metadata.json](models/metadata.json) |
| 6 | API FastAPI | [api/main.py](api/main.py), [api/logging_config.py](api/logging_config.py) |
| 7 | Tests Pytest | [tests/](tests/) – `test_api.py`, `test_data.py`, `test_model.py`, `test_logging.py` |
| 8 | Tests Selenium | [tests/test_selenium.py](tests/test_selenium.py) |
| 9 | Plan de test JMeter | [jmeter/churn_test_plan.jmx](jmeter/churn_test_plan.jmx) (charge / stress), [jmeter/endurance_test_plan.jmx](jmeter/endurance_test_plan.jmx) (endurance) + [résultats](jmeter/results/summary.md) |
| 10 | Dockerfile | [Dockerfile](Dockerfile) |
| 11 | docker-compose.yml | [docker-compose.yml](docker-compose.yml) |
| 12 | Pipeline GitHub Actions | [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| 13 | Configuration Prometheus | [monitoring/prometheus/](monitoring/prometheus/) |
| 14 | Dashboard Grafana | [monitoring/grafana/dashboards/ml-churn-api.json](monitoring/grafana/dashboards/ml-churn-api.json) |
| 15 | Configuration ELK | [docker/logstash/](docker/logstash/), [docker/kibana/](docker/kibana/) |
| 16 | Documentation technique | [docs/DOCUMENTATION_TECHNIQUE.md](docs/DOCUMENTATION_TECHNIQUE.md) |
| 17 | Guide d'installation | [docs/GUIDE_INSTALLATION.md](docs/GUIDE_INSTALLATION.md) |
| 18 | Rapport d'industrialisation | [docs/RAPPORT_INDUSTRIALISATION.md](docs/RAPPORT_INDUSTRIALISATION.md) |
| 19 | Présentation finale | [docs/PRESENTATION.md](docs/PRESENTATION.md) |
| + | Questions de soutenance | [docs/SOUTENANCE.md](docs/SOUTENANCE.md) |
| + | Déploiement VM | [deploy/deploy.sh](deploy/deploy.sh) |

## Corrections apportées au sujet

Le sujet demandait d'« apporter les corrections nécessaires » au pipeline fourni.
Les principales :

| Partie | Problème dans le code fourni | Correction |
|---|---|---|
| 4 | chemin de sortie relatif au dossier courant ; fins de ligne différentes Windows/Linux | chemins absolus, `lineterminator="\n"`, reproductibilité vérifiée en CI |
| 5 | `plt.show()` bloque (et plante sans écran en CI/Docker) | figures enregistrées, affichage seulement avec `--show` |
| 6 | Random Forest gardé d'office ; sélection impossible à justifier | validation croisée 5 plis, choix sur le F1, test réservé à l'évaluation finale |
| 6 | aucun versionnement du modèle | `metadata.json`, registre `models/registry/vX.Y.Z`, garde-fou qualité, non-promotion d'un modèle moins bon |
| 7 | liste passée au modèle au lieu d'un DataFrame (avertissement scikit-learn) | DataFrame avec les noms de colonnes de l'entraînement |
| 7 | `predict` et `predict_proba` appelés tous les deux | un seul calcul, classe déduite du seuil |
| 7 | version `1.0.0` écrite en dur à trois endroits | lue dans `metadata.json` |
| 7 | aucune validation des entrées, plantage au démarrage sans modèle | contraintes Pydantic (422), `/health` en 503 `DOWN` |
| 11 / 16 | `pytest` seul ne trouve pas le paquet `api` en CI | `pytest.ini` avec `pythonpath = .` |
| 16 | la CI lance les tests sans modèle ni données | génération + entraînement avant `pytest` |
| 12 | `git config` avec le nom de l'enseignant | identité de l'auteur du projet |
| 14 | `COPY . .` copie `.venv`, `.git`, données et tests ; exécution en root | `.dockerignore`, copie ciblée, utilisateur non root, HEALTHCHECK |
| 15 / 22 | Grafana lancé à part avec `docker run` : il ne voit pas Prometheus | tous les services dans le même docker-compose |
| 17 | `assert "FastAPI" in driver.title` échoue toujours (titre « Churn Prediction API - Swagger UI ») | assertion corrigée, tests E2E sur une vraie interface |
| 17 | le test Selenium casserait `pytest` en CI (pas de serveur ni de navigateur) | marqueur `e2e`, job CI dédié |
| 19 | logs texte, difficiles à exploiter dans Kibana | logs JSON répondant à quand / qui / quoi / quel modèle / résultat / durée / erreur |
| 20 | compose ELK et configuration Logstash non fournis | pipeline Logstash, template d'index, dashboard Kibana importé automatiquement |
| 3 | `pip freeze` sous Windows mélange outils de dev et dépendances de l'API | `requirements.txt` (API) et `requirements-dev.txt` |

Le détail et les mesures sont dans le [rapport d'industrialisation](docs/RAPPORT_INDUSTRIALISATION.md).

## Résultats du modèle

| Modèle | F1 (CV 5 plis) | ROC-AUC (CV) | F1 (test) | ROC-AUC (test) |
|---|---|---|---|---|
| **Logistic Regression** (retenu) | **0,523** | **0,655** | 0,510 | 0,636 |
| Decision Tree | 0,436 | 0,624 | 0,545 | 0,623 |
| Random Forest | 0,488 | 0,622 | 0,485 | 0,625 |

Le signal des données générées est faible par construction (le churn est tiré au
hasard avec une probabilité comprise entre 20 % et 70 %) : ces scores modestes sont
attendus. La régression logistique l'emporte parce que le générateur est lui-même
une fonction logistique. Le Random Forest du sujet reste disponible avec
`python src/train.py --model random_forest`.
