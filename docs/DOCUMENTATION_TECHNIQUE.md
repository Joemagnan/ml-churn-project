# Documentation technique

Projet fil rouge MLOps – prédiction du churn télécom – Joe MAGNAN – MDSIA 2

## 1. Architecture

```
                         UTILISATEUR
                              │
                              ▼
                ┌───────────────────────────┐
                │ Interface web (Nginx)     │  :8080  frontend/
                │ proxy /api/ → api:8000    │
                └─────────────┬─────────────┘
                              ▼
                ┌───────────────────────────┐
                │ FastAPI  /predict /health │  :8000  api/main.py
                │ /model/info /metrics /ui  │
                └──────┬───────────┬────────┘
                       │           │
          models/model.pkl     logs JSON (volume api-logs)        /metrics
          + metadata.json          │                                 │
                                   ▼                                 ▼
                       Logstash ─► Elasticsearch ─► Kibana     Prometheus ─► Grafana
                                    :9200            :5601       :9090        :3000
```

Tous les services sont décrits dans `docker-compose.yml` et partagent le réseau
`ml-churn_default` : chaque service joint les autres par son nom (`api`,
`prometheus`, `elasticsearch`…).

## 2. Arborescence

```
ml-churn-project/
├── .github/workflows/ci.yml      Pipeline CI/CD GitHub Actions
├── api/
│   ├── main.py                   API FastAPI (endpoints, métriques, middleware de logs)
│   ├── logging_config.py         Logs JSON (fichier + sortie standard)
│   └── serve.py                  Lanceur de production (workers uvicorn + TCP_NODELAY)
├── data/raw/churn.csv            Dataset (généré, versionné)
├── data/*.png                    Figures de l'exploration
├── deploy/deploy.sh              Déploiement sur VM Linux
├── docker/
│   ├── nginx/                    Image de l'interface web + proxy
│   ├── logstash/                 Pipeline Logstash + template d'index Elasticsearch
│   └── kibana/                   Vue de données, visualisations, dashboard (import auto)
├── docs/                         Documentation, guide, rapport, soutenance
├── frontend/                     Interface web (HTML, CSS, JavaScript)
├── jmeter/                       Plan de test, scripts, résultats des campagnes
├── models/
│   ├── model.pkl                 Modèle en production
│   ├── metadata.json             Version, métriques, date, empreinte des données
│   └── registry/vX.Y.Z/          Historique local des versions (non versionné)
├── monitoring/
│   ├── prometheus/               Configuration, règles d'alerte, Dockerfile
│   └── grafana/                  Source de données, dashboard, Dockerfile
├── notebooks/                    exploration.py (sujet) + exploration.ipynb (exécuté)
├── reports/metrics.json          Comparaison des trois modèles
├── src/
│   ├── generate_data.py          Génération du dataset
│   └── train.py                  Entraînement, sélection, versionnement, garde-fou
├── tests/                        Pytest (unitaires, API, logs, modèle) + Selenium
├── Dockerfile                    Image de l'API
├── docker-compose.yml            Stack complète
├── pytest.ini                    Configuration des tests
├── requirements.txt              Dépendances de l'API
└── requirements-dev.txt          Dépendances de développement et de test
```

## 3. Données

`src/generate_data.py` reprend le générateur du sujet (graine 42, 2 000 clients).

| Variable | Type | Plage | Effet sur le churn dans le générateur |
|---|---|---|---|
| `age` | entier | 18–69 | aucun |
| `anciennete` | entier (mois) | 1–119 | −0,015 par mois (effet principal) |
| `revenu` | entier (FCFA) | 150 000–999 999 | aucun |
| `nb_reclamations` | entier (Poisson λ=2) | 0–10 | +0,04 par réclamation |
| `montant_mensuel` | entier (FCFA) | 5 000–74 999 | +0,00001 par FCFA |
| `retards_paiement` | entier (Poisson λ=1) | 0–6 | +0,08 par retard |
| `churn` | 0/1 | 43 % de 1 | cible |

Le churn est tiré au hasard selon `p = sigmoïde(score)`, avec p entre 20 % et 70 % environ.
Le signal est donc faible par construction : un ROC-AUC d'environ 0,65 est le
maximum raisonnable. Le CSV est écrit avec des fins de ligne LF : il est identique
sous Windows et Linux, et la CI vérifie qu'il est reproductible (`git diff --exit-code`).

## 4. Entraînement (`src/train.py`)

1. Contrôle du schéma : colonnes attendues, absence de valeurs manquantes, cible binaire.
2. Découpage train/test 80/20, **stratifié** sur `churn`, `random_state=42`.
3. Trois pipelines scikit-learn : `StandardScaler + LogisticRegression`,
   `DecisionTreeClassifier(max_depth=5)` et `RandomForestClassifier(200 arbres)`.
4. Validation croisée stratifiée à 5 plis sur le jeu d'entraînement (F1, ROC-AUC,
   accuracy) ; **le modèle retenu est celui qui a le meilleur F1 moyen en validation croisée**.
5. Évaluation finale sur le jeu de test : accuracy, précision, rappel, F1, ROC-AUC,
   matrice de confusion.
6. Garde-fou qualité : si le F1 test est inférieur à `--min-f1` (0,45 par défaut), le
   script s'arrête avec le code 1 et la CI échoue.
7. Versionnement : la version est archivée dans `models/registry/v<version>/`, puis
   **promue** dans `models/model.pkl` seulement si son F1 n'est pas inférieur de plus
   de `--tolerance` (0,01) à celui du modèle en production (`--force` pour passer outre).

Résultats (jeu de test de 400 clients) :

| Modèle | F1 CV | ROC-AUC CV | F1 test | ROC-AUC test | Accuracy test |
|---|---|---|---|---|---|
| **Logistic Regression** (retenu) | **0,523** | **0,655** | 0,510 | 0,636 | 0,625 |
| Decision Tree | 0,436 | 0,624 | 0,545 | 0,623 | 0,633 |
| Random Forest | 0,488 | 0,622 | 0,485 | 0,625 | 0,603 |

`models/metadata.json` contient le nom du modèle, sa version, la date d'entraînement,
les métriques, la liste des variables, le seuil, l'empreinte SHA-256 du dataset et
les versions de Python et scikit-learn.

## 5. API (`api/main.py`)

| Méthode | Endpoint | Rôle | Codes |
|---|---|---|---|
| GET | `/` | Informations sur l'application | 200 |
| GET | `/health` | Vivacité : l'API répond et le modèle est chargé | 200 `UP` / 503 `DOWN` |
| GET | `/model/info` | Modèle servi : nom, version, métriques, variables, seuil | 200 |
| POST | `/predict` | Prédiction pour un client | 200 / 422 / 500 / 503 |
| GET | `/metrics` | Métriques Prometheus | 200 |
| GET | `/docs` | Swagger UI | 200 |
| GET | `/ui/` | Interface web (développement et CI) | 200 |

Requête `/predict` (validée par Pydantic : âge 18–100, valeurs positives) :

```json
{"age": 35, "anciennete": 5, "revenu": 450000, "nb_reclamations": 2,
 "montant_mensuel": 25000, "retards_paiement": 2}
```

Réponse (`duration_ms` = temps de calcul du modèle) :

```json
{"prediction": "CHURN", "probability": 0.599, "model_version": "1.0.0", "duration_ms": 0.9}
```

Exécution en production (`python -m api.serve`, commande de l'image Docker) :
`WEB_CONCURRENCY` workers uvicorn (4 par défaut) partageant une socket d'écoute avec
`TCP_NODELAY`, sans log d'accès uvicorn, avec les en-têtes de proxy acceptés.
Prometheus fonctionne alors en mode multiprocessus (`PROMETHEUS_MULTIPROC_DIR`,
vidé à chaque démarrage) et chaque worker écrit son propre fichier de logs
(`api-<pid>.log`). En développement, `uvicorn api.main:app --reload` reste valable.

Choix d'implémentation :
- le modèle est chargé une seule fois, au démarrage ; s'il est absent, l'API démarre
  quand même mais `/health` renvoie 503 (le conteneur passe alors `unhealthy`) ;
- l'entrée est convertie en DataFrame avec les noms de colonnes de l'entraînement ;
- `predict_proba` est appelé une seule fois et la classe déduite du seuil enregistré ;
- l'endpoint est synchrone (`def`) : FastAPI l'exécute dans un pool de threads et ne
  bloque pas la boucle d'événements pendant le calcul ;
- chaque réponse renvoie un en-tête `X-Request-ID`, repris dans les logs.

## 6. Logs (PARTIES 19 et 20)

Chaque requête HTTP produit **une seule** ligne JSON (le middleware l'enrichit avec
le résultat de la prédiction), écrite sur la sortie standard (`docker compose logs api`)
et dans `/app/logs/api-<pid>.log` (volume `api-logs`, rotation à 10 Mo, 3 fichiers par
worker). Une ligne supplémentaire de niveau ERROR est écrite en cas d'erreur du modèle.

```json
{"timestamp": "2026-11-07T23:16:42.067+00:00", "level": "INFO", "service": "ml-churn-api",
 "logger": "ml_churn", "message": "Prediction request: model_version=1.0.0",
 "operation": "predict", "method": "POST", "endpoint": "/predict", "status_code": 200,
 "response_time_ms": 2.4, "client_id": "web-ui", "client_ip": "172.21.0.1",
 "request_id": "fc71ca7cb7fe42af", "model_version": "1.0.0", "model_name": "Logistic Regression",
 "prediction": "NO_CHURN", "probability": 0.2013, "model_time_ms": 0.9}
```

| Question du sujet | Champ(s) |
|---|---|
| Quand ? | `timestamp` → `@timestamp` dans Elasticsearch |
| Qui ? | `client_id` (en-tête `X-Client-ID`), `client_ip`, `request_id` |
| Quelle opération ? | `operation` (`predict`, `http_request`, `load_model`), `method`, `endpoint` |
| Quel modèle ? | `model_name`, `model_version` |
| Quel résultat ? | `prediction`, `probability`, `status_code` |
| Combien de temps ? | `response_time_ms` (requête complète), `model_time_ms` (modèle seul) |
| Quelle erreur ? | `level: ERROR`, `error`, `error_detail` (trace complète) |

Les données personnelles du client (âge, revenu…) ne sont **pas** journalisées (un test le vérifie).

Chaîne ELK : Logstash lit le fichier en continu (`file` input, codec JSON), recale
`@timestamp` sur l'heure de l'API, ajoute le tag `error` aux erreurs et écrit dans
l'index quotidien `ml-churn-logs-AAAA.MM.JJ`. Un template d'index type les champs
(`probability` et `response_time_ms` en float, `prediction` et `model_version` en keyword).

Le service `kibana-setup` importe au démarrage :
- la vue de données `ml-churn-logs-*` ;
- les recherches « Prédictions de churn », « Erreurs de l'API », « Requêtes HTTP » ;
- le dashboard **« ML Churn API – Logs »** : nombre de prédictions, nombre d'erreurs,
  répartition CHURN / NO_CHURN, prédictions par version du modèle, temps de réponse,
  requêtes par endpoint, tableau des erreurs.

Exemples de requêtes KQL dans Discover : `operation : "predict" and prediction : "CHURN"`,
`level : "ERROR" or status_code >= 500`, `model_version : "1.0.0"`, `response_time_ms > 100`.

## 7. Métriques (PARTIES 21 et 22)

| Métrique | Type | Origine | Usage |
|---|---|---|---|
| `http_requests_total{handler,method,status}` | counter | Instrumentator | requêtes, erreurs (`status="5xx"`), taux d'erreur |
| `http_request_duration_seconds_bucket{handler}` | histogram | Instrumentator | temps de réponse p50 / p95 / p99 |
| `churn_predictions_total{prediction,model_version}` | counter | API | nombre de prédictions par classe |
| `churn_prediction_errors_total` | counter | API | erreurs du modèle |
| `churn_prediction_duration_seconds` | histogram | API | durée du calcul du modèle seul |
| `churn_prediction_probability` | histogram | API | distribution des scores (dérive) |
| `churn_model_info{model_name,model_version}` | gauge | API | modèle servi |
| `up{job="ml-churn-api"}` | gauge | Prometheus | disponibilité |

Prometheus interroge `api:8000/metrics` toutes les 5 s. Règles d'alerte
(`monitoring/prometheus/alerts.yml`, visibles dans Prometheus > Alerts) : API
indisponible, taux de 5xx supérieur à 5 %, p95 de `/predict` supérieur à 500 ms,
probabilité moyenne prédite hors de [0,20 ; 0,65].

Dashboard Grafana **« ML Churn API – Monitoring »** (provisionné) : état de l'API,
nombre de requêtes, nombre de prédictions, nombre d'erreurs, taux d'erreur, modèle
en production, requêtes/s par endpoint, temps de réponse p50/p95/p99, erreurs par
code, prédictions par classe, probabilité moyenne, durée du calcul du modèle.

## 8. Tests

| Fichier | Type | Ce qui est vérifié |
|---|---|---|
| `tests/test_api.py` | API | les 4 tests du sujet + format, validation (422), modèle absent (503), erreur modèle (500), métriques, Swagger, interface |
| `tests/test_data.py` | unitaire | schéma, plages, reproductibilité, CSV versionné identique au générateur |
| `tests/test_model.py` | unitaire + intégration | artefacts versionnés, garde-fou qualité, non-promotion d'un modèle moins bon, qualité du modèle en production |
| `tests/test_logging.py` | unitaire | format JSON, champs « qui / quoi / quand », une ligne par prédiction, fichier par worker, absence de données personnelles, erreurs en ERROR |
| `tests/test_serve.py` | unitaire | lanceur : 1 worker sans supervision, N workers avec `TCP_NODELAY` |
| `tests/test_selenium.py` | E2E (`-m e2e`) | Swagger, statut de l'API dans l'interface, scénario saisie → prédiction → résultat, message d'erreur |

`pytest` lance les tests unitaires, API et d'intégration ; les tests Selenium sont
exclus par défaut (marqueur `e2e`) car ils demandent une API démarrée et Chrome.

## 9. CI/CD (`.github/workflows/ci.yml`)

| Job | Déclencheur | Étapes |
|---|---|---|
| `tests` | push / PR sur main, develop, feature/** | installation → génération des données + contrôle de reproductibilité → entraînement avec garde-fou → pytest + couverture → artefacts |
| `e2e` | après `tests` | API lancée sur le runner → Selenium Chrome headless |
| `docker` | après `tests` | `docker compose config` → build de l'image → stack api + frontend + Prometheus + Grafana → tests d'intégration (health, predict, proxy Nginx, cible Prometheus `up`, dashboard Grafana) |
| `publish` | push sur `main`, après `e2e` et `docker` | build et push de `ghcr.io/joemagnan/ml-churn-api:{latest, version, sha}` |

## 10. Sécurité et limites

- L'API tourne avec un utilisateur non root ; l'image ne contient ni les tests, ni les données, ni `.git`.
- `joblib.load` peut exécuter du code : ne charger que des modèles produits par la chaîne du projet.
- Elasticsearch et Kibana tournent sans authentification (`xpack.security.enabled=false`) :
  acceptable en TP, à activer avant toute exposition sur Internet.
- Grafana : changer `GRAFANA_ADMIN_PASSWORD` en dehors du poste de développement.
- Capacité mesurée et montée en charge : voir le rapport d'industrialisation
  (tests de charge avant et après optimisation).
